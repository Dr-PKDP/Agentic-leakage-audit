def test_guard_allows_screening_feature():
    from src.feature_guard import classify_feature

    result = classify_feature("RIDAGEYR")

    assert result["status"] == "allowed"


def test_guard_blocks_blood_pressure_measurement():
    from src.feature_guard import classify_feature

    result = classify_feature("BPXSY1")

    assert result["status"] == "forbidden"


def test_guard_blocks_hypertension_diagnosis_item():
    from src.feature_guard import classify_feature

    result = classify_feature("BPQ020")

    assert result["status"] == "forbidden"


def test_guard_excludes_survey_weight_from_predictors():
    from src.feature_guard import classify_feature

    result = classify_feature("WTMEC2YR")

    assert result["status"] == "metadata"


def test_guard_requires_review_for_unknown_feature():
    from src.feature_guard import classify_feature

    result = classify_feature("LAB_UNSEEN")

    assert result["status"] == "review_required"

def test_guard_allows_smoking_questionnaire_feature():
    from src.feature_guard import classify_feature

    result = classify_feature("SMAQUEX2")

    assert result["status"] == "allowed"


def test_guard_allows_weight_history_questionnaire_feature():
    from src.feature_guard import classify_feature

    result = classify_feature("WHQ070")

    assert result["status"] == "allowed"
def test_guard_rejects_metadata_as_predictor():
    import pytest

    from src.feature_guard import assert_predictors_allowed

    with pytest.raises(ValueError, match="WTMEC2YR"):
        assert_predictors_allowed(["RIDAGEYR", "WTMEC2YR"])


def test_guard_rejects_target_as_predictor():
    import pytest

    from src.feature_guard import assert_predictors_allowed

    with pytest.raises(ValueError, match="undiagnosed_hypertension"):
        assert_predictors_allowed(
            ["RIDAGEYR", "undiagnosed_hypertension"]
        )