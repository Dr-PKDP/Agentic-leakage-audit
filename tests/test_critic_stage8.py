import pandas as pd


def test_check_cycle_separation_passes_for_disjoint_sets():
    from src.critic_stage8 import check_cycle_separation

    result = check_cycle_separation(
        training_cycles=["2011-2012", "2013-2014"],
        calibration_cycle="2015-2016",
        later_cycle="2021-2023",
    )

    assert result["status"] == "pass"


def test_check_cycle_separation_fails_for_overlap():
    from src.critic_stage8 import check_cycle_separation

    result = check_cycle_separation(
        training_cycles=["2011-2012", "2015-2016"],
        calibration_cycle="2015-2016",
        later_cycle="2021-2023",
    )

    assert result["status"] == "fail"


def test_check_required_metrics_passes_when_all_exist():
    from src.critic_stage8 import check_required_metrics

    metrics = {
        "weighted_roc_auc": 0.65,
        "weighted_average_precision": 0.25,
        "weighted_brier_score": 0.15,
        "calibration_slope": 1.0,
        "calibration_intercept": 0.0,
    }

    result = check_required_metrics(metrics)

    assert result["status"] == "pass"


def test_check_predictors_passes_for_allowed_features():
    from src.critic_stage8 import check_predictors

    result = check_predictors(["RIDAGEYR", "ALQ130", "phq9_total"])

    assert result["status"] == "pass"


def test_check_predictors_fails_for_forbidden_feature():
    from src.critic_stage8 import check_predictors

    result = check_predictors(["RIDAGEYR", "BPXSY1"])

    assert result["status"] == "fail"


def test_check_later_cycle_role_rejects_invalid_role():
    from src.critic_stage8 import check_later_cycle_role

    result = check_later_cycle_role("final_test")

    assert result["status"] == "fail"