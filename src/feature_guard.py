from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = REPO_ROOT / "configs" / "hypertension_feature_guard.yaml"


def load_guard() -> dict:
    return yaml.safe_load(GUARD_PATH.read_text(encoding="utf-8"))


def classify_feature(feature: str, guard: dict | None = None) -> dict[str, str]:
    guard = guard or load_guard()

    if feature in guard["target_columns"]:
        return {
            "feature": feature,
            "status": "target",
            "reason": "Outcome label; never a predictor.",
        }

    if feature in guard["metadata_columns"]:
        return {
            "feature": feature,
            "status": "metadata",
            "reason": "Identifier or survey-design field; never a predictor.",
        }

    if feature in guard["forbidden_exact"]:
        return {
            "feature": feature,
            "status": "forbidden",
            "reason": "Explicitly prohibited leakage feature.",
        }

    if feature.startswith(tuple(guard["forbidden_prefixes"])):
        return {
            "feature": feature,
            "status": "forbidden",
            "reason": "Prohibited leakage-prone feature family.",
        }

    if feature in guard["allowed_derived_features"]:
        return {
            "feature": feature,
            "status": "allowed",
            "reason": "Approved derived screening feature.",
        }

    if feature.endswith("__missing"):
        base_feature = feature.removesuffix("__missing")
        base_result = classify_feature(base_feature, guard)
        if base_result["status"] == "allowed":
            return {
                "feature": feature,
                "status": "allowed",
                "reason": "Missingness indicator for an approved feature.",
            }
        return {
            "feature": feature,
            "status": base_result["status"],
            "reason": f"Indicator inherits base-feature status: {base_result['reason']}",
        }

    if feature.startswith(tuple(guard["allowed_feature_prefixes"])):
        return {
            "feature": feature,
            "status": "allowed",
            "reason": "Approved screening-time feature family.",
        }

    return {
        "feature": feature,
        "status": guard["policy"]["default_for_unlisted_features"],
        "reason": "Feature is not in an approved family and requires review.",
    }


def audit_features(columns: list[str], guard: dict | None = None) -> pd.DataFrame:
    guard = guard or load_guard()
    return pd.DataFrame([classify_feature(column, guard) for column in columns])


def assert_predictors_allowed(
    predictors: list[str],
    guard: dict | None = None,
) -> None:
    guard = guard or load_guard()
    audit = audit_features(predictors, guard)

    blocked = audit.loc[
        audit["status"].isin(
            ["forbidden", "review_required", "metadata", "target"]
        )
    ]

    if not blocked.empty:
        details = blocked[["feature", "status", "reason"]].to_dict("records")
        raise ValueError(f"Guard blocked predictor set: {details}")


def main() -> None:
    feature_path = (
        REPO_ROOT
        / "outputs"
        / "features"
        / "P6_STAGE6_hypertension_features_minimal.csv"
    )
    output_path = (
        REPO_ROOT
        / "outputs"
        / "features"
        / "P6_hypertension_feature_guard_audit.csv"
    )

    df = pd.read_csv(feature_path, nrows=1)
    audit = audit_features(df.columns.tolist())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_path, index=False)

    print(output_path)
    print(audit["status"].value_counts().to_string())

    predictor_audit = audit.loc[audit["status"].eq("allowed")]
    assert_predictors_allowed(predictor_audit["feature"].tolist())


if __name__ == "__main__":
    main()