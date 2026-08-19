#!/usr/bin/env python3
"""Bedrock-backed agent for local real-model evaluation of attack.py.

Implements AgentProtocol against Amazon Bedrock converse API so we can run
the real gpt-oss-20b / gemma-3-27b models locally (same family as the hosted
targets) and measure actual fire rates / scores without a 15h submission.

Usage: see local_eval.py
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import requests

from aicomp_sdk.agents.types import (
    AgentDecision,
    AgentStateSnapshot,
    AgentToolSpec,
    FinalResponseDecision,
    ToolCall,
    ToolCallDecision,
)
from aicomp_sdk.agents.types import (
    AssistantMessageEvent,
    ToolRequestEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from aicomp_sdk.core.runtime_history import RuntimeHistory

_REGION = "us-east-1"
_MODEL_IDS = {
    "gpt_oss": "openai.gpt-oss-20b-1:0",
    "gemma": "google.gemma-3-27b-it",
}


def _api_key() -> str:
    key_path = Path(__file__).resolve().parents[1] / "BEDROCK_API_KEY.txt"
    return key_path.read_text().strip().split("=", 1)[1]


def _sanitize_tool_name(name: str) -> str:
    # Bedrock tool names: [a-zA-Z0-9_-]+
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


class BedrockAgent:
    """Minimal AgentProtocol implementation over Bedrock converse."""

    def __init__(self, model: str = "gpt_oss", max_tokens: int = 1024):
        self.model_id = _MODEL_IDS[model]
        self.max_tokens = max_tokens
        self._url = (
            f"https://bedrock-runtime.{_REGION}.amazonaws.com"
            f"/model/{self.model_id}/converse"
        )
        self._key = _api_key()

    # -- AgentProtocol ----------------------------------------------------
    def next_action(self, *, history: RuntimeHistory, tools) -> AgentDecision:
        messages = self._to_messages(history)
        tool_config = self._to_tool_config(tools)
        body: dict[str, Any] = {
            "messages": messages,
            "inferenceConfig": {"maxTokens": self.max_tokens, "temperature": 0.0},
        }
        system = self._system_text(history)
        if system:
            body["system"] = [{"text": system}]
        if tool_config:
            body["toolConfig"] = tool_config

        r = requests.post(
            self._url,
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        if r.status_code != 200:
            raise RuntimeError(f"bedrock {r.status_code}: {r.text[:300]}")
        return self._parse(r.json())

    def reset_state(self) -> None:
        pass

    def snapshot_state(self) -> AgentStateSnapshot:
        return {"version": 1, "backend": f"bedrock:{self.model_id}", "data": {}}

    def restore_state(self, snapshot: AgentStateSnapshot) -> None:
        pass

    # -- conversion helpers ----------------------------------------------
    def _system_text(self, history: RuntimeHistory) -> str:
        return "\n".join(e.text for e in history.instructions)

    def _to_messages(self, history: RuntimeHistory) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = []
        for e in history.events:
            if isinstance(e, UserMessageEvent):
                msgs.append({"role": "user",
                             "content": [{"text": e.text}]})
            elif isinstance(e, AssistantMessageEvent):
                msgs.append({"role": "assistant",
                             "content": [{"text": e.text}]})
            elif isinstance(e, ToolRequestEvent):
                msgs.append({"role": "assistant", "content": [{
                    "toolUse": {
                        "toolUseId": e.call.call_id,
                        "name": _sanitize_tool_name(e.call.tool_name),
                        "input": dict(e.call.arguments),
                    }}]})
            elif isinstance(e, ToolResultEvent):
                msgs.append({"role": "user", "content": [{
                    "toolResult": {
                        "toolUseId": e.result.call_id,
                        "content": [{"text": e.result.output_text}],
                        "status": "error" if e.result.is_error else "success",
                    }}]})
        return msgs

    def _to_tool_config(self, tools) -> dict[str, Any] | None:
        if not tools:
            return None
        return {"tools": [{
            "toolSpec": {
                "name": _sanitize_tool_name(t.name),
                "description": t.description,
                "inputSchema": {"json": dict(t.parameters_json_schema)},
            }} for t in tools]}

    def _parse(self, payload: dict[str, Any]) -> AgentDecision:
        msg = payload.get("output", {}).get("message", {})
        for block in msg.get("content", []):
            if "toolUse" in block:
                tu = block["toolUse"]
                # restore dotted tool name
                name = self._restore_tool_name(tu["name"])
                call = ToolCall(
                    call_id=tu.get("toolUseId", f"call_{uuid.uuid4().hex[:6]}"),
                    tool_name=name,
                    arguments=tu.get("input", {}),
                )
                return ToolCallDecision(call=call)
        # no tool use -> final response
        text = "".join(b.get("text", "") for b in msg.get("content", []))
        return FinalResponseDecision(text=text or "")

    _TOOL_NAMES = ["http.post", "fs.read", "fs.write", "fs.delete",
                   "shell.run", "email.send", "email.read", "web.open",
                   "web.search"]

    def _restore_tool_name(self, name: str) -> str:
        # map sanitized back to canonical dotted name by prefix match
        for canon in self._TOOL_NAMES:
            if _sanitize_tool_name(canon) == name:
                return canon
        return name
