#!/usr/bin/env python3
"""Ollama Cloud-backed agent (AgentProtocol) for local real-model eval.

Uses the SAME models as the hosted competition via Ollama Cloud's
llama.cpp backend: gpt-oss:20b (exact) and gemma4:31b (26b unavailable on
cloud; 31b is the closest Gemma-4 variant). This replaces Bedrock, whose
gemma-3 wrote code instead of calling tools.

OpenAI-compatible tool calling (/api/chat with tools + tool_calls).
"""
from __future__ import annotations

import json
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

_ENDPOINT = "https://ollama.com/api/chat"
_MODELS = {
    "gpt_oss": "gpt-oss:20b",
    "gemma": "gemma4:31b",
}


def _api_key() -> str:
    key_path = Path(__file__).resolve().parents[1] / "BEDROCK_API_KEY.txt"
    for line in key_path.read_text().splitlines():
        if line.startswith("OLLAMA_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("OLLAMA_API_KEY not found in key file")


def _sanitize_tool_name(name: str) -> str:
    return name.replace(".", "_")


class OllamaCloudAgent:
    """AgentProtocol over Ollama Cloud /api/chat (OpenAI tool-call format)."""

    def __init__(self, model: str = "gpt_oss", max_tokens: int = 1024):
        self.model = _MODELS[model]
        self.max_tokens = max_tokens
        self._key = _api_key()

    def next_action(self, *, history: RuntimeHistory, tools) -> AgentDecision:
        messages = self._to_messages(history)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": self.max_tokens},
        }
        system = "\n".join(e.text for e in history.instructions)
        if system:
            body["messages"] = [{"role": "system", "content": system}] + messages
        if tools:
            body["tools"] = self._to_tools(tools)

        r = requests.post(
            _ENDPOINT,
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"},
            json=body,
            timeout=180,
        )
        if r.status_code != 200:
            raise RuntimeError(f"ollama {r.status_code}: {r.text[:300]}")
        return self._parse(r.json())

    def reset_state(self) -> None:
        pass

    def snapshot_state(self) -> AgentStateSnapshot:
        return {"version": 1, "backend": f"ollama:{self.model}", "data": {}}

    def restore_state(self, snapshot: AgentStateSnapshot) -> None:
        pass

    def _to_messages(self, history: RuntimeHistory) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = []
        for e in history.events:
            if isinstance(e, UserMessageEvent):
                msgs.append({"role": "user", "content": e.text})
            elif isinstance(e, AssistantMessageEvent):
                msgs.append({"role": "assistant", "content": e.text})
            elif isinstance(e, ToolRequestEvent):
                msgs.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": e.call.call_id,
                        "function": {
                            "name": _sanitize_tool_name(e.call.tool_name),
                            "arguments": dict(e.call.arguments),
                        },
                    }],
                })
            elif isinstance(e, ToolResultEvent):
                msgs.append({
                    "role": "tool",
                    "content": e.result.output_text,
                    "tool_call_id": e.result.call_id,
                })
        return msgs

    def _to_tools(self, tools) -> list[dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": _sanitize_tool_name(t.name),
                "description": t.description,
                "parameters": self._sanitize_schema(dict(t.parameters_json_schema)),
            },
        } for t in tools]

    @staticmethod
    def _sanitize_schema(schema: dict[str, Any]) -> dict[str, Any]:
        """Strip JSON-Schema constructs Ollama's tool-call grammar rejects.

        email.list has anyOf:[integer,null] / anyOf:[string,null] for its
        optional limit/cursor args; llama.cpp's tool grammar chokes on
        anyOf ("can't find closing '}'"). Collapse anyOf to its first
        non-null branch (the args are optional-with-default anyway).
        """
        out = dict(schema)
        if "anyOf" in out:
            non_null = [b for b in out["anyOf"]
                        if b.get("type") != "null"]
            if non_null:
                first = non_null[0]
                out.pop("anyOf", None)
                out.update(first)
        props = out.get("properties")
        if isinstance(props, dict):
            out["properties"] = {
                k: OllamaCloudAgent._sanitize_schema(v)
                for k, v in props.items()
            }
        return out

    _TOOL_NAMES = ["http.post", "fs.read", "fs.write", "fs.delete",
                   "shell.run", "email.send", "email.read", "web.open",
                   "web.search"]

    def _restore_tool_name(self, name: str) -> str:
        for canon in self._TOOL_NAMES:
            if _sanitize_tool_name(canon) == name:
                return canon
        return name

    def _parse(self, payload: dict[str, Any]) -> AgentDecision:
        msg = payload.get("message", {})
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (TypeError, json.JSONDecodeError):
                args = fn.get("arguments", {})
            if not isinstance(args, dict):
                args = {}
            call = ToolCall(
                call_id=tc.get("id", f"call_{hash(fn.get('name','')) & 0xffff:04x}"),
                tool_name=self._restore_tool_name(fn.get("name", "")),
                arguments=args,
            )
            return ToolCallDecision(call=call)
        return FinalResponseDecision(text=msg.get("content", "") or "")
