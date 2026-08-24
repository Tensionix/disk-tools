from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_CORE = ROOT / "system_core"
for entry in (ROOT, SYSTEM_CORE):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
