import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pyreadstat

root = Path(os.environ["P6_DIR"])
config_path = root / "configs/nhanes_depression_dev_v4.json"
config_bytes = config_path.read_bytes()
config = json.loads(config_bytes)

if config["execution_permissions"].get("local_outcome_audit") is not True:
    raise SystemExit("STOP: outcome audit is not permitted by configuration.")


if config["execution_permissions"].get("local_split_audit") is not True:
    raise SystemExit("STOP: split audit is not permitted.")

if config["execution_permissions"].get("model_training") is not False:
    raise SystemExit("STOP: expected model training to remain disabled.")

if config["execution_permissions"].get("autonomous_generated_code") is not False:
    raise SystemExit("STOP: expected autonomous execution to remain disabled.")

evaluation = config["evaluation"]
expected = {
    "splitter": "StratifiedGroupKFold",
    "n_splits": 5,
    "shuffle": True,
    "random_state": 42,
    "group_fields": ["SDMVSTRA", "SDMVPSU"],
}
for key, value in expected.items():
    if evaluation.get(key) != value:
        raise SystemExit(f"STOP: unexpected split configuration for {key}.")

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


import warnings

import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import StratifiedGroupKFold

cohort = joined.loc[usable].reset_index(drop=True)
y = labels.loc[usable].astype(int).to_numpy()
group_fields = evaluation["group_fields"]

group_index = pd.MultiIndex.from_frame(cohort[group_fields])
groups, unique_groups = pd.factorize(group_index, sort=True)

n = len(y)
n_groups = len(unique_groups)
n_splits = evaluation["n_splits"]
coverage = np.zeros(n, dtype=int)
fold_reports = []
failures = []
warning_messages = []

report = {
    "task_id": config["task_id"],
    "status": "pending",
    "audit_type": "grouped_split_feasibility_only",
    "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
    "versions": {
        "scikit_learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyreadstat": pyreadstat.__version__,
    },
    "eligible_before_item_completeness": int(eligible.sum()),
    "eligible_with_missing_outcome": int((eligible & labels.isna()).sum()),
    "eligible_with_valid_outcome": n,
    "unweighted_class_counts": {
        "negative": int(np.sum(y == 0)),
        "positive": int(np.sum(y == 1)),
    },
    "distinct_groups": n_groups,
    "split_configuration": {
        key: evaluation[key]
        for key in (
            "splitter", "n_splits", "shuffle",
            "random_state", "group_fields",
        )
    },
    "folds": fold_reports,
    "checks": {},
    "warnings": warning_messages,
    "failures": failures,
    "participant_level_output_saved": False,
    "model_training_performed": False,
    "preprocessing_fitted": False,
    "predictive_performance_evaluated": False,
    "limitations": [
        "All class counts and fractions are unweighted.",
        "Passing establishes only the checked split-feasibility conditions.",
        "No predictor set, estimator, or evaluation protocol is approved.",
        "Outcome-completeness selection remains unresolved.",
        "Released design groups do not establish complete household or geographic independence.",
        "No population inference or design-aware uncertainty is computed.",
    ],
}

if n == 0:
    failures.append("No eligible participants with valid outcomes.")
if n_groups < n_splits:
    failures.append("Fewer distinct groups than requested folds.")
if len(np.unique(y)) != 2:
    failures.append("The eligible cohort does not contain both outcome classes.")

def partition_summary(indices):
    values = y[indices]
    count = len(indices)
    positive = int(np.sum(values == 1))
    return {
        "participants": count,
        "distinct_groups": int(len(np.unique(groups[indices]))),
        "negative": int(np.sum(values == 0)),
        "positive": positive,
        "unweighted_positive_fraction": positive / count if count else None,
    }

if not failures:
    splitter = StratifiedGroupKFold(
        n_splits=n_splits,
        shuffle=evaluation["shuffle"],
        random_state=evaluation["random_state"],
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            for fold, (train, heldout) in enumerate(
                splitter.split(np.zeros((n, 1)), y, groups), start=1
            ):
                coverage[heldout] += 1
                group_overlap = np.intersect1d(
                    groups[train], groups[heldout]
                ).size
                participant_overlap = np.intersect1d(train, heldout).size
                train_summary = partition_summary(train)
                heldout_summary = partition_summary(heldout)

                checks = {
                    "both_classes_in_training": (
                        train_summary["negative"] > 0
                        and train_summary["positive"] > 0
                    ),
                    "both_classes_in_heldout": (
                        heldout_summary["negative"] > 0
                        and heldout_summary["positive"] > 0
                    ),
                    "no_group_overlap": bool(group_overlap == 0),
                    "no_participant_overlap": bool(participant_overlap == 0),
                    "partitions_cover_cohort": bool(
                        np.union1d(train, heldout).size == n
                    ),
                }
                fold_reports.append({
                    "fold": fold,
                    "training": train_summary,
                    "heldout": heldout_summary,
                    "overlapping_group_count": int(group_overlap),
                    "checks": checks,
                })
                for check, passed in checks.items():
                    if not passed:
                        failures.append(f"Fold {fold}: {check} failed.")
        except Exception as exc:
            failures.append(
                f"Splitter failed: {type(exc).__name__}: {exc}"
            )
        warning_messages.extend(str(w.message) for w in caught)

checks = {
    "enough_distinct_groups": bool(n_groups >= n_splits),
    "requested_fold_count_generated": len(fold_reports) == n_splits,
    "both_classes_in_every_training_and_heldout_partition": (
        len(fold_reports) == n_splits
        and all(
            f["checks"]["both_classes_in_training"]
            and f["checks"]["both_classes_in_heldout"]
            for f in fold_reports
        )
    ),
    "no_group_overlap_in_any_fold": (
        len(fold_reports) == n_splits
        and all(f["checks"]["no_group_overlap"] for f in fold_reports)
    ),
    "exactly_one_heldout_assignment_per_participant": bool(
        n > 0 and np.all(coverage == 1)
    ),
}
report["checks"] = checks
report["heldout_assignment_coverage"] = {
    "zero_assignments": int(np.sum(coverage == 0)),
    "one_assignment": int(np.sum(coverage == 1)),
    "multiple_assignments": int(np.sum(coverage > 1)),
}
for check, passed in checks.items():
    if not passed:
        failures.append(f"Overall check failed: {check}.")

report["status"] = (
    "PASS_FEASIBILITY_ONLY" if not failures else "FAIL_STOP_AND_REVIEW"
)

out = root / "outputs/data_inspection"
out.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
path = out / f"depression_split_audit_{stamp}.json"
text = json.dumps(report, indent=2, allow_nan=False)
with path.open("x", encoding="utf-8") as file:
    file.write(text + "\n")

print(text)
print("\nSaved aggregate audit:", path)
print("No models fitted; no participant-level assignments saved.")
if failures:
    raise SystemExit(1)
