"""AI Agent Security Competition — P2 attack submission.

Two-phase attacker:
  Phase 1 — pure-function enumeration of candidate families (no env cost).
  Phase 2 — timeboxed live search using eval_predicates (real-model signal).

See docs/superpowers/specs/2026-08-13-attack-algorithm-design.md.
"""
from __future__ import annotations

import time
from typing import Final

from aicomp_sdk.attacks import AttackAlgorithmBase, AttackCandidate, AttackRunConfig
from aicomp_sdk.core.predicates import eval_predicates

# --- hard constraints (mirror aicomp_sdk core; enforced locally too) ---
SECRET_MARKER: Final[str] = "SECRET_MARKER"
HOSTED_MAX_TOOL_HOPS: Final[int] = 8
MAX_CANDIDATES: Final[int] = 2000
MAX_MESSAGES_PER_CANDIDATE: Final[int] = 32
MAX_MESSAGE_CHARS: Final[int] = 2000


class AttackAlgorithm(AttackAlgorithmBase):
    """Attack search algorithm. Filled in by later tasks."""

    def run(self, env, config: AttackRunConfig) -> list[AttackCandidate]:
        return []


if __name__ == "__main__":  # pragma: no cover
    from pathlib import Path
    from aicomp_sdk.evaluation.ops import build_attack_env
    from aicomp_sdk.agents import build_agent  # re-exported from agents/__init__
    from aicomp_sdk.guardrails.optimal import Guardrail as OptimalGuardrail

    fixtures = Path(__file__).resolve().parents[1].parent / (
        "ai-agent-security-multi-step-tool-attacks/aicomp_sdk/fixtures"
    )
    e = build_attack_env(
        seed=123,
        fixtures_dir=fixtures,
        agent_factory=lambda: build_agent("deterministic"),
        guardrail=OptimalGuardrail(),
        env_selection="gym",
        max_tool_hops=8,
    )
    print("findings:", len(AttackAlgorithm().run(e, AttackRunConfig(time_budget_s=5))))
