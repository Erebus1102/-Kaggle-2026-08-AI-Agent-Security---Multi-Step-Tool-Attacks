#!/usr/bin/env python3
"""Local real-model evaluation for attack.py using Bedrock gpt-oss/gemma.

Measures the ACTUAL fire rate of message templates against the real models,
so design choices (plain vs forged, single vs multi-post) can be validated
locally instead of via 15h blind submissions.

Run from workspace/:
  AICOMP_ROOT=... PYTHONPATH=... .venv/bin/python local_eval.py
"""
from __future__ import annotations

import os
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

from bedrock_agent import BedrockAgent
import attack

FIXTURES = AICOMP / "aicomp_sdk" / "fixtures"


def make_env(model: str):
    return build_attack_env(
        seed=123,
        fixtures_dir=FIXTURES,
        agent_factory=lambda: BedrockAgent(model),
        guardrail=OptimalGuardrail(),
        env_selection="gym",
        max_tool_hops=8,
    )


def probe(env, msg: str) -> dict:
    """Run one message; return fire + post-count diagnostics."""
    env.reset()
    t0 = time.monotonic()
    env.interact(msg, max_tool_hops=8)
    elapsed = time.monotonic() - t0
    trace = env.export_trace_dict()
    preds = eval_predicates(trace)
    events = trace.get("tool_events", [])
    posts = [e for e in events if e.get("name") == "http.post" and e.get("ok")]
    return {
        "fired": bool(preds),
        "predicates": [p["predicate"] for p in preds],
        "n_posts": len(posts),
        "n_tools": len(events),
        "elapsed_s": round(elapsed, 2),
    }


def main():
    url = "https://report.example.org/log"
    urls = [f"https://{w}.example.org/log" for w in
            ("report", "metrics", "status", "collect")][:4]

    cases = {
        "plain_single": attack.post_msg(url),
        "forged_single": attack.forged_post_msg(url),
        "forged_multi4": attack.forged_multipost_msg(urls),
    }

    for model in ("gpt_oss", "gemma"):
        print(f"\n{'='*60}\nMODEL: {model}\n{'='*60}")
        env = make_env(model)
        for name, msg in cases.items():
            try:
                r = probe(env, msg)
                print(f"  {name:16s} fired={r['fired']} "
                      f"n_posts={r['n_posts']} n_tools={r['n_tools']} "
                      f"elapsed={r['elapsed_s']}s preds={r['predicates']}")
            except Exception as e:
                print(f"  {name:16s} ERROR {str(e)[:200]}")


if __name__ == "__main__":
    main()
