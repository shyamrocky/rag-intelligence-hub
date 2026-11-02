"""Canonical Master Dashboard launcher; app.py remains sealed historical replay.

Use the single documented localhost:8514 launch command in README.md.
Existing pages are retained; the runner adds read-only execution observability.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    from tools.generation_runner.ui import main

    main(ROOT)
