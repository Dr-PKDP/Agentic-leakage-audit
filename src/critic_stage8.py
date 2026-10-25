from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

try:
    from src.feature_guard import assert_predictors_allowed
except ModuleNotFoundError:
    from feature_guard import assert_predictors_allowed


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "configs" / "stage8_hypertension_recalibration_protocol.yaml"
SUMMARY_PATH = (
    REPO_ROOT
    / "outputs"
    / "models"
    / "P6_STAGE8_hypertension_recalibration_summary.json"
)
FEATURE_PATH = (
    REPO_ROOT
    / "outputs"
    / "features"
    / "P6_STAGE6_hypertension_features_minimal.csv"
)
GUARD_AUDIT_PATH = (
    REPO_ROOT
    / "outputs"
    / "features"
    / "P6_hypertension_feature_guard_audit.csv"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "models"
    / "P6_STAGE8_hypertension_critic_report.json"
)

REQUIRED_METRICS = [
    "weighted_roc_auc",
    "weighted_average_precision",
    "weighted_brier_score",
    "calibration_slope",
    "calibration_intercept",
]


def result(
    check: str,
    status: str,
    details: str,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "details": details,
    }


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_cycle_separation(
    training_cycles: list[str],
    calibration_cycle: str,
    later_cycle: str,
) -> dict[str, str]:
    training = set(training_cycles)

    if calibration_cycle in training:
        return result(
            "cycle_separation",
            "fail",
            "Calibration cycle overlaps training cycles.",
        )

    if later_cycle in training or later_cycle == calibration_cycle:
        return result(
            "cycle_separation",
            "fail",
            "Later descriptive cycle overlaps a fitting cycle.",
        )

    return result(
        "cycle_separation",
        "pass",
        "Training, calibration, and later descriptive cycles are disjoint.",
    )


def check_required_metrics(metrics: dict) -> dict[str, str]:
    missing = [name for name in REQUIRED_METRICS if name not in metrics]

    if missing:
        return result(
            "required_metrics",
            "fail",
            f"Missing metrics: {missing}",
        )

    null_metrics = [
        name for name in REQUIRED_METRICS
        if metrics[name] is None
    ]

    if null_metrics:
        return result(
            "required_metrics",
            "fail",
            f"Null metrics: {null_metrics}",
        )

    return result(
        "required_metrics",
        "pass",
        "All required discrimination and calibration metrics are present.",
    )


def check_predictors(predictors: list[str]) -> dict[str, str]:
    try:
        assert_predictors_allowed(predictors)
    except ValueError as error:
        return result(
            "leakage_guard",
            "fail",
            str(error),
        )

    return result(
        "leakage_guard",
        "pass",
        f"All {len(predictors)} predictors are approved by the leakage guard.",
    )


def check_survey_fields_not_predictors(
    predictors: list[str],
    protocol: dict,
) -> dict[str, str]:
    survey = protocol["survey_design"]
    prohibited = {
        survey["weight"],
        survey["strata"],
        survey["psu"],
    }
    found = sorted(prohibited.intersection(predictors))

    if found:
        return result(
            "survey_metadata_exclusion",
            "fail",
            f"Survey fields incorrectly included as predictors: {found}",
        )

    return result(
        "survey_metadata_exclusion",
        "pass",
        "Weight, strata, and PSU are excluded from predictors.",
    )


def check_later_cycle_role(role: str) -> dict[str, str]:
    expected = "descriptive_only_previously_accessed"

    if role != expected:
        return result(
            "later_cycle_role",
            "fail",
            f"Expected '{expected}', found '{role}'.",
        )

    return result(
        "later_cycle_role",
        "pass",
        "Later cycle is labeled descriptive-only and previously accessed.",
    )


def check_file(path: Path, label: str) -> dict[str, str]:
    if path.exists():
        return result(
            f"{label}_artifact",
            "pass",
            f"Found: {path.relative_to(REPO_ROOT)}",
        )

    return result(
        f"{label}_artifact",
        "fail",
        f"Missing: {path.relative_to(REPO_ROOT)}",
    )


def get_predictors(protocol: dict) -> list[str]:
    df = pd.read_csv(FEATURE_PATH, nrows=1)
    excluded = set(
        protocol["id_columns"]
        + protocol["excluded_from_predictors"]
    )
    return [column for column in df.columns if column not in excluded]


def main() -> None:
    protocol = load_yaml(PROTOCOL_PATH)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    predictors = get_predictors(protocol)

    checks = [
        check_file(PROTOCOL_PATH, "protocol"),
        check_file(SUMMARY_PATH, "summary"),
        check_file(GUARD_AUDIT_PATH, "guard_audit"),
        check_cycle_separation(
            protocol["training_cycles"],
            protocol["calibration_cycle"],
            protocol["previously_accessed_temporal_evaluation_cycle"],
        ),
        check_predictors(predictors),
        check_survey_fields_not_predictors(predictors, protocol),
        check_required_metrics(summary["calibration_raw_metrics"]),
        check_required_metrics(summary["calibration_platt_metrics"]),
        check_later_cycle_role(summary["later_cycle_role"]),
    ]

    overall_status = (
        "pass"
        if all(item["status"] == "pass" for item in checks)
        else "fail"
    )

    report = {
        "project": protocol["project"],
        "stage": protocol["stage"],
        "task": protocol["task"],
        "overall_status": overall_status,
        "predictor_count": len(predictors),
        "checks": checks,
        "limitations": [
            (
                "2021-2023 labels were accessed in Stage 7; Stage 8 labels "
                "are therefore descriptive-only, not a pristine final test."
            ),
            (
                "Point estimates use MEC sample weights; bootstrap intervals "
                "are not a substitute for full NHANES design-based variance "
                "estimation with strata and PSUs."
            ),
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()