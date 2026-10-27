import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

if importlib.util.find_spec("pandas") is None:
    raise SystemExit(
        "STOP: pandas is not installed. Report this message before proceeding."
    )

import pandas as pd
import pyreadstat

root = Path(os.environ["P6_DIR"])
raw = root / "data/raw/nhanes/2017_2018"
output = root / "outputs/data_inspection"
output.mkdir(parents=True, exist_ok=True)

report = {
    "purpose": "local aggregate inspection using pyreadstat",
    "reader": "pyreadstat.read_xport",
    "reader_version": pyreadstat.__version__,
    "cycle": "2017-2018",
    "files": {}
}
tables = {}

for name in ("DEMO_J", "DPQ_J"):
    path = raw / f"{name}.xpt"
    if not path.exists():
        raise SystemExit(f"STOP: missing file: {path}")

    table, metadata = pyreadstat.read_xport(str(path))
    tables[name] = table

    if "SEQN" not in table:
        raise SystemExit(f"STOP: SEQN missing from {name}.")

    report["files"][name] = {
        "rows": int(len(table)),
        "columns": list(table.columns),
        "missing_seqn": int(table["SEQN"].isna().sum()),
        "duplicate_seqn": int(table["SEQN"].duplicated().sum())
    }

demo = tables["DEMO_J"]
dpq = tables["DPQ_J"]

design_fields = [
    "WTINT2YR", "WTMEC2YR", "SDMVSTRA", "SDMVPSU"
]
report["demographic_fields"] = {}

for field in ["RIDAGEYR"] + design_fields:
    if field not in demo:
        report["demographic_fields"][field] = {"present": False}
        continue

    series = demo[field]
    entry = {
        "present": True,
        "missing": int(series.isna().sum()),
        "minimum": float(series.min()) if series.notna().any() else None,
        "maximum": float(series.max()) if series.notna().any() else None
    }
    if field.startswith("WT"):
        entry["zero_or_negative"] = int((series <= 0).sum())
    report["demographic_fields"][field] = entry

items = [f"DPQ{i:03d}" for i in range(10, 100, 10)]
missing_items = [field for field in items if field not in dpq]
if missing_items:
    raise SystemExit(f"STOP: expected depression items missing: {missing_items}")

report["depression_item_counts"] = {}

for field in items:
    series = dpq[field]
    counts = series.value_counts(dropna=True).sort_index()
    report["depression_item_counts"][field] = {
        "response_counts": {
            str(float(code)): int(count)
            for code, count in counts.items()
        },
        "missing": int(series.isna().sum()),
        "unexpected_nonmissing_codes": [
            float(code)
            for code in counts.index
            if code not in {0, 1, 2, 3, 7, 9}
        ]
    }

valid_items = dpq[items].isin([0, 1, 2, 3])
report["item_completeness"] = {
    "rows_with_all_nine_items_in_0_to_3": int(valid_items.all(axis=1).sum()),
    "rows_with_any_refused_or_dont_know": int(
        dpq[items].isin([7, 9]).any(axis=1).sum()
    ),
    "rows_with_any_missing_item": int(
        dpq[items].isna().any(axis=1).sum()
    ),
    "note": "Descriptive counts only; no eligibility or outcome rule applied."
}

demo_ids = set(demo["SEQN"].dropna())
dpq_ids = set(dpq["SEQN"].dropna())
report["identifier_overlap"] = {
    "dpq_unique_identifiers": len(dpq_ids),
    "dpq_identifiers_absent_from_demo": len(dpq_ids - demo_ids)
}

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
path = output / f"nhanes_2017_2018_readstat_{stamp}.json"
with path.open("x") as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write("\n")

print(json.dumps(report, indent=2, allow_nan=False))
print("\nSaved aggregate inspection:", path)
print("No participant rows displayed, no merge, no outcome, no model request.")
