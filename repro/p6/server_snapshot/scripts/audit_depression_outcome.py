import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pyreadstat

root = Path(os.environ["P6_DIR"])
config_path = root / "configs/nhanes_depression_dev_v1.json"
config_bytes = config_path.read_bytes()
config = json.loads(config_bytes)

if config["execution_permissions"].get("local_outcome_audit") is not True:
    raise SystemExit("STOP: outcome audit is not permitted by configuration.")

raw = root / "data/raw/nhanes/2017_2018"
demo, _ = pyreadstat.read_xport(str(raw / "DEMO_J.xpt"))
dpq, _ = pyreadstat.read_xport(str(raw / "DPQ_J.xpt"))

for name, table in (("DEMO_J", demo), ("DPQ_J", dpq)):
    if table["SEQN"].isna().any() or table["SEQN"].duplicated().any():
        raise SystemExit(f"STOP: invalid identifiers in {name}.")

fields = [
    "SEQN", "RIDAGEYR", "WTMEC2YR", "SDMVSTRA", "SDMVPSU"
]
joined = dpq.merge(
    demo[fields],
    on="SEQN",
    how="left",
    validate="one_to_one",
    indicator=True
)

if not joined["_merge"].eq("both").all():
    raise SystemExit("STOP: unmatched identifiers.")

items = config["outcome"]["items"]
allowed = config["outcome"]["valid_item_values"]
threshold = config["outcome"]["positive_threshold"]

if len(items) != 9 or len(set(items)) != 9:
    raise SystemExit("STOP: expected nine distinct outcome items.")

unexpected = {}
for item in items:
    values = joined[item]
    bad = values.notna() & ~values.isin(allowed + [7, 9])
    if bad.any():
        unexpected[item] = sorted(values[bad].unique().tolist())

if unexpected:
    raise SystemExit(f"STOP: unexpected item codes: {unexpected}")

eligible = joined["RIDAGEYR"].ge(
    config["population"]["minimum_age"]
)
if config["population"]["require_positive_mec_weight"]:
    eligible &= joined["WTMEC2YR"].gt(0)
if config["population"]["require_design_fields_present"]:
    eligible &= joined[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)

valid = joined[items].isin(allowed).all(axis=1)
score = joined[items].where(joined[items].isin(allowed)).sum(
    axis=1, min_count=len(items)
)

if not score.notna().equals(valid):
    raise SystemExit("STOP: completeness and score availability disagree.")

if not score.dropna().between(0, 27).all():
    raise SystemExit("STOP: score outside 0–27.")
if not score.dropna().mod(1).eq(0).all():
    raise SystemExit("STOP: non-integer score.")

labels = score.ge(threshold).astype("Int64").where(score.notna())
usable = eligible & labels.notna()

positive = int(labels[usable].eq(1).sum())
negative = int(labels[usable].eq(0).sum())
usable_count = int(usable.sum())

if positive + negative != usable_count:
    raise SystemExit("STOP: class-count reconciliation failed.")
if labels[~valid].notna().any():
    raise SystemExit("STOP: incomplete items received an outcome.")

distribution = (
    score[eligible & valid].value_counts().sort_index()
)

report = {
    "task_id": config["task_id"],
    "status": "development_only",
    "reader": "pyreadstat.read_xport",
    "reader_version": pyreadstat.__version__,
    "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
    "joined_rows": int(len(joined)),
    "eligible_before_item_completeness": int(eligible.sum()),
    "eligible_with_valid_outcome": usable_count,
    "eligible_with_missing_outcome": int((eligible & labels.isna()).sum()),
    "positive_threshold": threshold,
    "unweighted_class_counts": {
        "negative": negative,
        "positive": positive
    },
    "unweighted_positive_fraction": (
        positive / usable_count if usable_count else None
    ),
    "score_range_among_eligible_complete_records": {
        "minimum": int(score[usable].min()) if usable_count else None,
        "maximum": int(score[usable].max()) if usable_count else None
    },
    "unweighted_score_distribution": {
        str(int(value)): int(count)
        for value, count in distribution.items()
    },
    "checks": {
        "incomplete_items_have_no_outcome": True,
        "scores_integer_and_in_0_to_27": True,
        "class_counts_reconcile": True
    },
    "limitations": [
        "Counts and positive fraction are unweighted.",
        "No population prevalence estimate is reported.",
        "Incomplete-item exclusions may introduce selection bias.",
        "No predictor set or evaluation protocol has been approved."
    ],
    "participant_level_output_saved": False,
    "model_training_performed": False
}

out = root / "outputs/data_inspection"
out.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
path = out / f"depression_outcome_audit_{stamp}.json"

with path.open("x") as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write("\n")

print(json.dumps(report, indent=2, allow_nan=False))
print("\nSaved aggregate audit:", path)
print("Raw files unchanged; outcomes existed in memory only.")
