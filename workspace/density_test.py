#!/usr/bin/env python3
"""Density measurement on Bedrock gpt-oss: raw points per replay-second.

This is the core predictability data: which template maximizes raw/s.
Run from workspace/.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
AICOMP = REPO / "ai-agent-security-multi-step-tool-attacks"
sys.path.insert(0, str(AICOMP))
sys.path.insert(0, str(HERE))

from aicomp_sdk.evaluation.ops import build_attack_env
from aicomp_sdk.guardrails.optimal import Guardrail as OptimalGuardrail
from aicomp_sdk.core.predicates import eval_predicates
from aicomp_sdk.scoring import SEVERITY_W

from bedrock_agent import BedrockAgent
import attack

FIXTURES = AICOMP / "aicomp_sdk" / "fixtures"


def make_env():
    return build_attack_env(
        seed=123,
        fixtures_dir=FIXTURES,
        agent_factory=lambda: BedrockAgent("gpt_oss"),
        guardrail=OptimalGuardrail(),
        env_selection="gym",
        max_tool_hops=8,
    )


def probe_raw(env, msg: str, hops: int) -> dict:
    env.reset()
    t0 = time.monotonic()
    env.interact(msg, max_tool_hops=hops)
    elapsed = time.monotonic() - t0
    trace = env.export_trace_dict()
    preds = eval_predicates(trace)
    raw = sum(SEVERITY_W.get(int(p["severity"]), 1) for p in preds)
    posts = sum(1 for e in trace.get("tool_events", [])
                if e.get("name") == "http.post" and e.get("ok"))
    return {"raw": raw, "posts": posts, "elapsed": round(elapsed, 2),
            "preds": [p["predicate"] for p in preds]}


def main():
    url = "https://report.example.org/log"
    urls4 = [f"https://{w}.example.org/log" for w in
             ("report", "metrics", "status", "collect")]
    urls6 = [f"https://{w}.example.org/log" for w in
             ("report", "metrics", "status", "collect", "sync", "submit")]

    cases = {
        "plain_1": attack.post_msg(url),
        "forged_1": attack.forged_post_msg(url),
        "forged_multi2": attack.forged_multipost_msg(urls4[:2]),
        "forged_multi4": attack.forged_multipost_msg(urls4),
        "forged_multi6": attack.forged_multipost_msg(urls6),
    }

    env = make_env()
    print("template            raw  posts  elapsed  raw/s")
    print("-" * 55)
    for name, msg in cases.items():
        try:
            r = probe_raw(env, msg, hops=8)
            density = r["raw"] / r["elapsed"] if r["elapsed"] else 0
            print(f"{name:18s} {r['raw']:4d}  {r['posts']:3d}   "
                  f"{r['elapsed']:6.2f}s  {density:5.2f}")
        except Exception as e:
            print(f"{name:18s} ERROR {str(e)[:150]}")


if __name__ == "__main__":
    main()
