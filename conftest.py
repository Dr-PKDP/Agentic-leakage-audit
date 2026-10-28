import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for sub in ("", "experiments/preliminary_study", "experiments/core_contexts", "experiments/label_contexts", "analysis"):
    sys.path.insert(0, str(ROOT / sub) if sub else str(ROOT))
