import argparse
import csv
import hashlib
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/data/pduttapramanik/p6_vllm")
sys.path.insert(0, str(ROOT))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

parser = argparse.ArgumentParser()
parser.add_argument("--config-sha256", required=True)
args = parser.parse_args()

config_path = ROOT / "configs/nhanes_depression_dev_v7.json"
if sha(config_path) != args.config_sha256:
    raise SystemExit("STOP: configuration hash mismatch.")

config = json.loads(config_path.read_text())
permissions = config["execution_permissions"]

if (
    permissions.get("model_training") is not True
    or permissions.get("local_baseline_fit") is not True
    or permissions.get("autonomous_generated_code") is not False
    or permissions.get("participant_level_output") is not False
):
    raise SystemExit("STOP: authorization boundary mismatch.")

for name, expected in config["reference_source_sha256"].items():
    if sha(ROOT / name) != expected:
        raise SystemExit(f"STOP: source hash mismatch: {name}")

import numpy as np
import pandas as pd
import pyreadstat
import sklearn
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from src.depression_baseline_fit_v1 import fit_reference
from src.depression_secondary_v1 import fit_secondary_reference
from src.depression_execution_v1 import check_contract, check_row_alignment

check_contract(config)

expected_split = {
    "splitter": "StratifiedGroupKFold",
    "n_splits": 5,
    "shuffle": True,
    "random_state": 42,
    "group_fields": ["SDMVSTRA", "SDMVPSU"],
    "comparison_arms": ["primary", "age_gender"],
}
for key, value in expected_split.items():
    if config["evaluation"].get(key) != value:
        raise SystemExit(f"STOP: unexpected split setting: {key}")

started = time.perf_counter()
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
folder = ROOT / "outputs/reference_evaluation" / f"depression_{stamp}"
folder.mkdir(parents=True, exist_ok=False)

report = {
    "task_id": config["task_id"],
    "status": "STARTED",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "config_sha256": args.config_sha256,
    "runner_sha256": sha(Path(__file__)),
    "source_sha256": config["reference_source_sha256"],
    "versions": {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "pyreadstat": pyreadstat.__version__,
    },
    "authorization": config["reference_run_authorization"],
    "participant_level_output_saved": False,
    "fitted_models_saved": False,
    "autonomous_agent_execution": False,
    "protocol_frozen": False,
}

def require(condition, message):
    if not bool(condition):
        raise ValueError(message)

try:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        raw = ROOT / "data/raw/nhanes/2017_2018"
        paths = {
            "DEMO_J": raw / "DEMO_J.xpt",
            "DPQ_J": raw / "DPQ_J.xpt",
        }
        report["input_sha256"] = {
            name: sha(path) for name, path in paths.items()
        }

        demo, _ = pyreadstat.read_xport(str(paths["DEMO_J"]))
        dpq, _ = pyreadstat.read_xport(str(paths["DPQ_J"]))

        for table in (demo, dpq):
            require(
                table["SEQN"].notna().all()
                and not table["SEQN"].duplicated().any(),
                "Invalid input identifiers."
            )

        fields = [
            "SEQN", "RIDAGEYR", "RIAGENDR", "INDFMPIR",
            "WTMEC2YR", "SDMVSTRA", "SDMVPSU",
        ]
        joined = dpq.merge(
            demo[fields], on="SEQN", how="left",
            validate="one_to_one", indicator=True,
        )
        require(joined["_merge"].eq("both").all(), "Unmatched input records.")

        items = config["outcome"]["items"]
        allowed = config["outcome"]["valid_item_values"]
        require(
            items == [
                "DPQ010", "DPQ020", "DPQ030", "DPQ040", "DPQ050",
                "DPQ060", "DPQ070", "DPQ080", "DPQ090",
            ]
            and allowed == [0, 1, 2, 3]
            and config["outcome"]["positive_threshold"] == 10,
            "Unexpected outcome definition."
        )
        require(
            joined[items].apply(
                lambda values: values.isna() | values.isin(allowed + [7, 9])
            ).all().all(),
            "Unexpected nonmissing DPQ response code."
        )

        population = config["population"]
        require(
            population["minimum_age"] == 18
            and population["require_positive_mec_weight"] is True
            and population["require_design_fields_present"] is True,
            "Unexpected population definition."
        )

        eligible = (
            joined["RIDAGEYR"].ge(18)
            & joined["WTMEC2YR"].gt(0)
            & joined[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)
        )
        complete = joined[items].isin(allowed).all(axis=1)
        score = joined[items].where(
            joined[items].isin(allowed)
        ).sum(axis=1, min_count=9)

        require(score.notna().equals(complete), "Outcome completeness mismatch.")
        require(score.dropna().between(0, 27).all(), "Invalid outcome score.")

        cohort = joined.loc[eligible & complete].copy()
        cohort.index = pd.Index(cohort["SEQN"], name="SEQN")
        X = cohort[["RIDAGEYR", "RIAGENDR", "INDFMPIR"]].copy()
        y = score.loc[eligible & complete].ge(10).astype(int)
        y.index = cohort.index
        weights = cohort["WTMEC2YR"].copy()

        check_row_alignment(X, y, weights)
        require(
            len(cohort) == 5068
            and int(y.sum()) == 459
            and int(eligible.sum()) == 5533
            and int((eligible & ~complete).sum()) == 465
            and int(X["INDFMPIR"].isna().sum()) == 630,
            "Cohort does not reconcile with the audited counts."
        )

        # Preserve the original audit's sorted stratum–PSU coding.
        pairs = pd.MultiIndex.from_frame(cohort[["SDMVSTRA", "SDMVPSU"]])
        groups, unique_groups = pd.factorize(pairs, sort=True)
        require(len(unique_groups) == 30, "Group count differs from audit.")

        splitter = StratifiedGroupKFold(
            n_splits=5, shuffle=True, random_state=42
        )
        splits = list(splitter.split(np.zeros((len(X), 1)), y, groups))

        old_audit_path = (
            ROOT / "outputs/data_inspection/"
            "depression_predictor_fold_audit_20261025T043127048932Z.json"
        )
        old_audit = json.loads(old_audit_path.read_text())
        require(old_audit["status"] == "PASS_AUDIT_ONLY", "Prior audit failed.")
        require(
            old_audit["config_sha256"] ==
            "0e68c1165cf6e113fc11b4ee9dca4021fef8744455435ca29154d0738db45aa1",
            "Unexpected prior audit provenance."
        )
        report["prior_audit_sha256"] = sha(old_audit_path)

        labels = y.to_numpy()
        w = weights.to_numpy(dtype=float)
        coverage = np.zeros(len(X), dtype=int)
        fold_summaries = []

        # Validate every fold before the first model is fitted.
        for fold, (train, heldout) in enumerate(splits, start=1):
            require(
                not np.intersect1d(train, heldout).size
                and np.union1d(train, heldout).size == len(X),
                "Invalid participant partition."
            )
            require(
                not np.intersect1d(groups[train], groups[heldout]).size,
                "Group overlap."
            )
            require(
                set(np.unique(labels[train])) == {0, 1}
                and set(np.unique(labels[heldout])) == {0, 1},
                "Single-class partition."
            )
            require(
                X.iloc[train]["INDFMPIR"].notna().any(),
                "All training income is missing."
            )

            previous = old_audit["folds"][fold - 1]
            for indices, name in ((train, "training"), (heldout, "heldout")):
                require(
                    len(indices) == previous[name]["participants"]
                    and int(labels[indices].sum()) == previous[name]["positive"]
                    and len(np.unique(groups[indices])) ==
                    previous[name]["distinct_groups"],
                    "Fold counts differ from prior audit."
                )

            coverage[heldout] += 1
            fold_summaries.append({
                "fold": fold,
                "training_rows": len(train),
                "heldout_rows": len(heldout),
                "training_positive": int(labels[train].sum()),
                "heldout_positive": int(labels[heldout].sum()),
                "training_groups": len(np.unique(groups[train])),
                "heldout_groups": len(np.unique(groups[heldout])),
            })

        require(np.all(coverage == 1), "Invalid held-out coverage.")

        predictions = {
            arm: np.full(len(X), np.nan)
            for arm in ("primary", "age_gender", "intercept_only")
        }

        for fold, (train, heldout) in enumerate(splits, start=1):
            print(f"Fitting fold {fold}/5", flush=True)
            for arm, columns, fitting in (
                (
                    "primary",
                    ["RIDAGEYR", "RIAGENDR", "INDFMPIR"],
                    fit_reference,
                ),
                (
                    "age_gender",
                    ["RIDAGEYR", "RIAGENDR"],
                    fit_secondary_reference,
                ),
            ):
                preprocessing, model = fitting(
                    X.iloc[train][columns], labels[train], w[train]
                )
                require(
                    np.array_equal(model.classes_, [0, 1]),
                    "Unexpected estimator class ordering."
                )
                probabilities = model.predict_proba(
                    preprocessing.transform(X.iloc[heldout][columns])
                )
                require(
                    probabilities.shape == (len(heldout), 2)
                    and np.isfinite(probabilities).all()
                    and ((probabilities >= 0) & (probabilities <= 1)).all()
                    and np.allclose(probabilities.sum(axis=1), 1),
                    "Invalid model probabilities."
                )
                predictions[arm][heldout] = probabilities[:, 1]
                fold_summaries[fold - 1][arm + "_iterations"] = int(
                    np.max(model.n_iter_)
                )

            predictions["intercept_only"][heldout] = np.average(
                labels[train], weights=w[train]
            )

        epsilon = float(np.finfo(np.float64).eps)
        metric_rows = []
        for arm, probability in predictions.items():
            require(
                np.isfinite(probability).all()
                and ((probability >= 0) & (probability <= 1)).all(),
                "Invalid or incomplete held-out predictions."
            )
            clipped = np.clip(probability.astype(np.float64), epsilon, 1 - epsilon)
            losses = -(
                labels * np.log(clipped)
                + (1 - labels) * np.log1p(-clipped)
            )
            squared_errors = (labels - probability) ** 2

            for weighting, metric_weights in (
                ("WTMEC2YR", w), ("unweighted", None)
            ):
                metric_rows.append({
                    "arm": arm,
                    "weighting": weighting,
                    "participants": len(X),
                    "AUROC": float(roc_auc_score(
                        labels, probability, sample_weight=metric_weights
                    )),
                    "Brier": float(np.average(
                        squared_errors, weights=metric_weights
                    )),
                    "log_loss": float(np.average(
                        losses, weights=metric_weights
                    )),
                })

        report.update({
            "status": "COMPLETED_FIXED_REFERENCE_DEVELOPMENT",
            "cohort": {
                "eligible_before_completeness": int(eligible.sum()),
                "missing_outcome": int((eligible & ~complete).sum()),
                "complete_outcome": len(X),
                "positive": int(labels.sum()),
                "negative": int((labels == 0).sum()),
                "groups": len(unique_groups),
            },
            "folds": fold_summaries,
            "metrics": metric_rows,
            "log_loss_clipping_epsilon": epsilon,
            "aggregation": "Pooled out-of-fold predictions, not mean fold metrics",
            "warnings": [
                {"category": item.category.__name__, "message": str(item.message)}
                for item in caught
            ],
            "limitations": [
                "Internal development only; no temporal or final test evaluation.",
                "No confidence intervals or significance tests.",
                "Weighted point estimates are not complete complex-survey inference.",
                "Complete-outcome selection remains unresolved.",
                "Processed-income real-time availability is not established.",
                "No agent benchmark or clinical validation is completed by this run.",
            ],
        })

        # Recheck raw inputs before declaring the run complete.
        require(
            all(sha(paths[name]) == digest
                for name, digest in report["input_sha256"].items()),
            "An input file changed during execution."
        )

        with (folder / "aggregate_metrics.csv").open(
            "x", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(file, fieldnames=list(metric_rows[0]))
            writer.writeheader()
            writer.writerows(metric_rows)

except Exception as exc:
    report["status"] = "FAILED_STOP_AND_REVIEW"
    report["failure"] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }

report["elapsed_seconds"] = time.perf_counter() - started
report["completed_utc"] = datetime.now(timezone.utc).isoformat()
with (folder / "run_report.json").open("x", encoding="utf-8") as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write("\n")

print("Status:", report["status"])
print("Saved aggregate artifacts:", folder)
if report["status"] != "COMPLETED_FIXED_REFERENCE_DEVELOPMENT":
    print("Failure:", report.get("failure"))
    raise SystemExit(1)

for row in report["metrics"]:
    print(
        f"{row['arm']:15s} {row['weighting']:10s} "
        f"AUROC={row['AUROC']:.6f} "
        f"Brier={row['Brier']:.6f} "
        f"log_loss={row['log_loss']:.6f}"
    )
print("Participant-level outputs and fitted models were NOT saved.")
print("Protocol remains unfrozen. No agent experiment was executed.")
