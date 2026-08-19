#!/usr/bin/env python3
"""Multi-sample density measurement on Ollama Cloud (same llama.cpp backend
as the hosted competition). Measures raw/回放秒 for each template × model,
median over N samples to kill cold-start noise.

Run from workspace/: .venv/bin/python density_test.py [N]
"""
from __future__ import annotations

import statistics
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

from ollama_cloud_agent import OllamaCloudAgent
import attack

FIXTURES = AICOMP / "aicomp_sdk" / "fixtures"


def make_env(model: str):
    return build_attack_env(
        seed=123,
        fixtures_dir=FIXTURES,
        agent_factory=lambda: OllamaCloudAgent(model),
        guardrail=OptimalGuardrail(),
        env_selection="gym",
        max_tool_hops=8,
    )


def probe(env, msg: str) -> dict:
    env.reset()
    t0 = time.monotonic()
    env.interact(msg, max_tool_hops=8)
    elapsed = time.monotonic() - t0
    trace = env.export_trace_dict()
    preds = eval_predicates(trace)
    raw = sum(SEVERITY_W.get(int(p["severity"]), 1) for p in preds)
    posts = sum(1 for e in trace.get("tool_events", [])
                if e.get("name") == "http.post" and e.get("ok"))
    return {"raw": raw, "posts": posts, "elapsed": elapsed}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    url = "https://report.example.org/log"
    urls4 = [f"https://{w}.example.org/log" for w in
             ("report", "metrics", "status", "collect")]

    cases = {
        "forged_1": attack.forged_post_msg(url),
        "plain_1": attack.post_msg(url),
        "forged_multi4": attack.forged_multipost_msg(urls4),
    }

    print(f"template         model     median_raw  posts  median_s  raw/s")
    print("-" * 68)
    for model in ("gpt_oss", "gemma"):
        env = make_env(model)
        for name, msg in cases.items():
            raws, posts, els = [], [], []
            for _ in range(n):
                try:
                    r = probe(env, msg)
                    raws.append(r["raw"]); posts.append(r["posts"])
                    els.append(r["elapsed"])
                except Exception as e:
                    print(f"  {name}/{model} ERR {str(e)[:80]}")
            if els:
                mr = statistics.median(raws)
                me = statistics.median(els)
                mp = statistics.median(posts)
                print(f"{name:16s} {model:8s} {mr:8d} {mp:5d} {me:9.2f}s "
                      f"{mr/me:5.2f}")


if __name__ == "__main__":
    main()
