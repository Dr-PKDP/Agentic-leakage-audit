from pathlib import Path

import yaml


def test_feature_spec_exists_and_is_parseable():
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "configs" / "stage6_hypertension_feature_spec.yaml"

    assert spec_path.exists()

    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    assert spec["outcome"] == "undiagnosed_hypertension"
    assert spec["primary_minimal_screening"]["demographics"]
    assert spec["expanded_health_history"]["medical_conditions"]


def test_feature_spec_forbids_bp_label_fields():
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "configs" / "stage6_hypertension_feature_spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    forbidden = set(spec["forbidden_predictors"])

    assert "mean_systolic_bp" in forbidden
    assert "mean_diastolic_bp" in forbidden
    assert "elevated_bp_130_80" in forbidden
    assert "known_hypertension" in forbidden
    assert "taking_hypertension_medication" in forbidden
    assert "undiagnosed_hypertension" in forbidden