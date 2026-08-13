"""pytest path setup so tests run without manual env vars."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = HERE.parent / "ai-agent-security-multi-step-tool-attacks"
sys.path.insert(0, str(HERE))   # `import attack` works
sys.path.insert(0, str(SDK))    # `import aicomp_sdk` works
