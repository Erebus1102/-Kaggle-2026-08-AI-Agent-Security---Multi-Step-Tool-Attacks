#!/usr/bin/env python3
"""Build `kaggle_cell2.py` — the cell-2 replacement for the forked official
starter notebook (`getting-started-notebook.ipynb`).

Run from `workspace/`:  python3 build_kaggle_cell2.py
Output: `kaggle_cell2.py` — paste its content into the forked notebook's cell 2
(replacing the starter's `attack_code = '''...'''` block entirely).

Why splice the path-setup header where we do: `from __future__ import
annotations` must precede every other statement, and the aicomp_sdk import must
follow the sys.path setup — so the header goes between them.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

HEADER = """import sys
import glob
from pathlib import Path

# Add competition data to path
for candidate in glob.glob('/kaggle/input/**/kaggle_evaluation', recursive=True):
    dataset_root = str(Path(candidate).parent)
    if dataset_root not in sys.path:
        sys.path.insert(0, dataset_root)
    break

"""

FUTURE = "from __future__ import annotations"


def build_embedded() -> str:
    attack_py = (HERE / "attack.py").read_text()
    idx = attack_py.index(FUTURE) + len(FUTURE)
    embedded = attack_py[:idx] + "\n\n" + HEADER + attack_py[idx:].lstrip("\n")
    assert "'''" not in embedded, "triple-single-quote collision with embedding"
    return embedded


def build_cell2() -> str:
    embedded = build_embedded()
    return (
        "attack_code = '''\n" + embedded + "'''\n\n"
        "with open('/kaggle/working/attack.py', 'w') as f:\n"
        "    f.write(attack_code)\n"
        "print('attack.py written ✅')\n"
        "\n"
        "# Placeholder so the submit API finds the expected output file during\n"
        "# commit runs; the real one is written by the gateway during reruns.\n"
        "import os\n"
        "if not os.getenv('KAGGLE_IS_COMPETITION_RERUN'):\n"
        "    with open('/kaggle/working/submission.csv', 'w') as f:\n"
        "        f.write('Id,Score\\n')\n"
        "    print('placeholder submission.csv written')"
    )


if __name__ == "__main__":
    cell2 = build_cell2()
    compile(cell2, "kaggle_cell2.py", "exec")  # fail fast on syntax errors
    (HERE / "kaggle_cell2.py").write_text(cell2)
    print(f"wrote kaggle_cell2.py ({len(cell2)} chars) — paste into notebook cell 2")
