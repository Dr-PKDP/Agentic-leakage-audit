import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for sub in ("", "experiments/pilot_depression", "experiments/principal_v0_4", "experiments/extended_v0_5", "analysis"):
    sys.path.insert(0, str(ROOT / sub) if sub else str(ROOT))
