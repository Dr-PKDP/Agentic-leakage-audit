import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pyreadstat

root = Path(os.environ["P6_DIR"])
raw = root / "data/raw/nhanes/2017_2018"
out = root / "outputs/data_inspection"
out.mkdir(parents=True, exist_ok=True)

demo, _ = pyreadstat.read_xport(str(raw / "DEMO_J.xpt"))
dpq, _ = pyreadstat.read_xport(str(raw / "DPQ_J.xpt"))

for name, table in (("DEMO_J", demo), ("DPQ_J", dpq)):
    if table["SEQN"].isna().any() or table["SEQN"].duplicated().any():
        raise SystemExit(f"STOP: invalid identifiers in {name}.")

fields = [
    "SEQN", "RIDAGEYR", "WTINT2YR",
    "WTMEC2YR", "SDMVSTRA", "SDMVPSU"
]

joined = dpq.merge(
    demo[fields],
    on="SEQN",
    how="left",
    validate="one_to_one",
    indicator=True
)

if not joined["_merge"].eq("both").all():
    raise SystemExit("STOP: unmatched depression-file identifiers.")

items = [f"DPQ{i:03d}" for i in range(10, 100, 10)]
complete = joined[items].isin([0, 1, 2, 3]).all(axis=1)
adult = joined["RIDAGEYR"].ge(18)
positive_weight = joined["WTMEC2YR"].gt(0)
design_present = joined[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)

report = {
    "purpose": "development-only join and eligibility audit",
    "reader": "pyreadstat.read_xport",
    "reader_version": pyreadstat.__version__,
    "joined_rows": int(len(joined)),
    "all_identifiers_matched": True,
    "age": {
        "missing": int(joined["RIDAGEYR"].isna().sum()),
        "minimum": float(joined["RIDAGEYR"].min()),
        "maximum": float(joined["RIDAGEYR"].max()),
        "under_18": int(joined["RIDAGEYR"].lt(18).sum())
    },
    "independent_counts": {
        "age_at_least_18": int(adult.sum()),
        "all_nine_items_valid": int(complete.sum()),
        "positive_mec_weight": int(positive_weight.sum()),
        "zero_mec_weight": int(joined["WTMEC2YR"].eq(0).sum()),
        "missing_mec_weight": int(joined["WTMEC2YR"].isna().sum()),
        "stratum_and_psu_present": int(design_present.sum())
    },
    "intersection_count": {
        "adult_complete_positive_mec_weight_design_present": int(
            (adult & complete & positive_weight & design_present).sum()
        ),
        "note": "Audit intersection only; not a frozen cohort definition."
    },
    "no_outcome_constructed": True,
    "no_participant_level_output_saved": True
}

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
path = out / f"nhanes_join_audit_{stamp}.json"
with path.open("x") as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write("\n")

print(json.dumps(report, indent=2))
print("\nSaved:", path)
print("Joined data existed in memory only; raw files unchanged.")
