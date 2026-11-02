"""Test-only helpers; never change application configuration on ordinary imports."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/regression"))
