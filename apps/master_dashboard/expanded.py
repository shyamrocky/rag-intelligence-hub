"""Current expanded experimental entry point; app.py remains historical replay."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.quality_dashboard.expanded_ui import main

main(ROOT)
