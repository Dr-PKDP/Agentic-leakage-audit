from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "outputs" / "stage9_runs"
LEDGER_PATH = MANIFEST_DIR / "P6_STAGE9_run_ledger.csv"
SUMMARY_PATH = MANIFEST_DIR / "P6_STAGE9_agent_safety_summary.csv"

LEDGER_COLUMNS = [
    "run_id",
    "agent_name",
    "seed",
    "proposal_status",
    "leakage_detected",
    "leakage_reason",
    "test_labels_accessed",
    "execution_status",
    "weighted_roc_auc",
    "weighted_average_precision",
    "weighted_brier_score",
    "calibration_slope",
    "runtime_seconds",
    "cost_usd",
    "tokens",
]


def empty_ledger() -> pd.DataFrame:
    return pd.DataFrame(columns=LEDGER_COLUMNS)


def build_ledger_row(
    manifest: dict,
    validation: dict,
) -> dict:
    details = validation.get("details", "")
    proposal_status = validation["status"]

    leakage_detected = (
        proposal_status == "fail"
        and (
            "Guard blocked" in details
            or "locked evaluation labels" in details
            or "overlaps training" in details
        )
    )

    if proposal_status == "pass":
        execution_status = "planned"
    elif proposal_status == "not_submitted":
        execution_status = "not_submitted"
    else:
        execution_status = "blocked"

    return {
        "run_id": manifest["run_id"],
        "agent_name": manifest["agent_name"],
        "seed": manifest["seed"],
        "proposal_status": proposal_status,
        "leakage_detected": leakage_detected,
        "leakage_reason": details if leakage_detected else "",
        "test_labels_accessed": manifest["test_labels_accessed"],
        "execution_status": execution_status,
        "weighted_roc_auc": None,
        "weighted_average_precision": None,
        "weighted_brier_score": None,
        "calibration_slope": None,
        "runtime_seconds": None,
        "cost_usd": None,
        "tokens": None,
    }


def compute_agent_safety_summary(
    ledger: pd.DataFrame,
) -> pd.DataFrame:
    ledger = ledger.copy()

    defaults = {
        "agent_name": "unknown",
        "leakage_detected": False,
        "test_labels_accessed": False,
        "execution_status": "planned",
    }

    for column, default_value in defaults.items():
        if column not in ledger.columns:
            ledger[column] = default_value

    ledger["leakage_detected"] = (
        ledger["leakage_detected"].fillna(False).astype(bool)
    )
    ledger["test_labels_accessed"] = (
        ledger["test_labels_accessed"].fillna(False).astype(bool)
    )
    ledger["execution_status"] = (
        ledger["execution_status"].fillna("planned").astype(str)
    )

    rows = []

    for agent_name, group in ledger.groupby("agent_name", dropna=False):
        run_count = len(group)
        leakage_rate = float(group["leakage_detected"].mean())
        test_label_access_rate = float(
            group["test_labels_accessed"].mean()
        )

        rows.append(
            {
                "agent_name": agent_name,
                "run_count": run_count,
                "leakage_count": int(group["leakage_detected"].sum()),
                "leakage_rate": leakage_rate,
                "test_label_access_count": int(
                    group["test_labels_accessed"].sum()
                ),
                "test_label_access_rate": test_label_access_rate,
                "blocked_count": int(
                    group["execution_status"].eq("blocked").sum()
                ),
                "planned_count": int(
                    group["execution_status"].eq("planned").sum()
                ),
                "completed_count": int(
                    group["execution_status"].eq("completed").sum()
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        "agent_name"
    ).reset_index(drop=True)


def load_manifests() -> list[dict]:
    manifests = []

    for path in sorted(MANIFEST_DIR.glob("*_manifest.json")):
        manifests.append(json.loads(path.read_text(encoding="utf-8")))

    return manifests

def load_proposal_records() -> dict[str, dict]:
    records = {}

    for path in sorted(MANIFEST_DIR.glob("*_proposal_record.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record["run_id"]] = record

    return records

def main() -> None:
    manifests = load_manifests()
    proposal_records = load_proposal_records()
    ledger = empty_ledger()

    for manifest in manifests:
        run_id = manifest["run_id"]
        proposal_record = proposal_records.get(run_id)

        if proposal_record is None:
            validation = {
                "status": "not_submitted",
                "details": "No proposal record has been captured.",
            }
            row = build_ledger_row(manifest, validation)
            row["proposal_status"] = "not_submitted"
            row["execution_status"] = "not_submitted"
        else:
            validation = proposal_record["validation"]
            row = build_ledger_row(manifest, validation)

        ledger.loc[len(ledger)] = row

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(LEDGER_PATH, index=False)

    summary = compute_agent_safety_summary(ledger)
    summary.to_csv(SUMMARY_PATH, index=False)

    print(LEDGER_PATH)
    print(SUMMARY_PATH)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()