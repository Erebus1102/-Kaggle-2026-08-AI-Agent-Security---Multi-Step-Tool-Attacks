# Task 1: Project setup (git + pytest harness + submission skeleton)

**Files:**
- Create: `.gitignore`
- Create: `workspace/conftest.py`
- Create: `workspace/tests/__init__.py` (empty)
- Modify: `workspace/attack.py` (replace starter template with skeleton)

**Interfaces:**
- Produces: `AttackAlgorithm` class (subclasses `AttackAlgorithmBase`) with `run(env, config) -> list[AttackCandidate]` returning `[]` for now. Later tasks fill it in.

- [ ] **Step 1: Initialize git and install pytest**

```bash
cd "/Users/renhaoliu/Desktop/Project/AI Agent Security - Multi-Step Tool Attacks"
git init
workspace/.venv/bin/pip install pytest
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.DS_Store
workspace/.aicomp/
workspace/evaluation_artifacts/
```

- [ ] **Step 3: Create `workspace/conftest.py`**

```python
"""pytest path setup so tests run without manual env vars."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = HERE.parent / "ai-agent-security-multi-step-tool-attacks"
sys.path.insert(0, str(HERE))   # `import attack` works
sys.path.insert(0, str(SDK))    # `import aicomp_sdk` works
```

- [ ] **Step 4: Create empty `workspace/tests/__init__.py`**

(empty file)

- [ ] **Step 5: Replace `workspace/attack.py` with the skeleton**

```python
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

    fixtures = Path(__file__).resolve().parents[1] / (
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
```

- [ ] **Step 6: Write the failing test `workspace/tests/test_run.py`**

```python
from attack import AttackAlgorithm
from aicomp_sdk.attacks import AttackRunConfig


class _FakeEnv:
    """Minimal env satisfying the protocol read by run()."""

    def __init__(self):
        self.seed = 123

    def reset(self, *a, **k):
        pass

    def interact(self, msg, max_tool_hops=None):
        return None

    def export_trace_dict(self):
        return {"tool_events": [], "user_messages": [], "egress": [], "seed": 123}

    def snapshot(self):
        return None

    def restore(self, s):
        pass


def test_run_returns_list_of_candidates():
    result = AttackAlgorithm().run(_FakeEnv(), AttackRunConfig(time_budget_s=1))
    assert isinstance(result, list)
```

- [ ] **Step 7: Run test to verify it passes**

```bash
cd workspace && ../.gitignore 2>/dev/null; .venv/bin/python -m pytest tests/test_run.py -v
```
Expected: PASS (1 test). If `import attack` fails, confirm `conftest.py` is at `workspace/conftest.py`.

- [ ] **Step 8: Validate the submission contract**

```bash
cd workspace
export AICOMP_ROOT="$PWD/../ai-agent-security-multi-step-tool-attacks"
export PYTHONPATH="$AICOMP_ROOT:$PYTHONPATH"
.venv/bin/aicomp validate redteam attack.py
```
Expected: validation passes (no output / success). The `aicomp` console script lives in `workspace/.venv/bin`; if missing, run `.venv/bin/pip install -e "$AICOMP_ROOT"`.

- [ ] **Step 9: Commit**

```bash
git add .gitignore CLAUDE.md workspace/attack.py workspace/conftest.py workspace/tests/
git commit -m "chore: scaffold attack.py submission + pytest harness"
```
