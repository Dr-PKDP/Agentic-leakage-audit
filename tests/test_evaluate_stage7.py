import numpy as np
import pandas as pd


def test_weighted_quantile_bins_has_requested_bin_count():
    from src.evaluate_stage7 import weighted_quantile_bins

    probabilities = pd.Series([0.10, 0.20, 0.30, 0.40, 0.50, 0.60])
    weights = pd.Series([1.0] * 6)

    result = weighted_quantile_bins(probabilities, weights, n_bins=3)

    assert len(result) == 6
    assert result.notna().all()
    assert result.nunique() == 3


def test_weighted_calibration_table_has_expected_observed_rate():
    from src.evaluate_stage7 import weighted_calibration_table

    df = pd.DataFrame(
        {
            "undiagnosed_hypertension": [0, 1, 0, 1],
            "predicted_risk": [0.10, 0.20, 0.80, 0.90],
            "WTMEC2YR": [1.0, 1.0, 1.0, 1.0],
        }
    )

    result = weighted_calibration_table(
        df,
        target="undiagnosed_hypertension",
        probability="predicted_risk",
        weight="WTMEC2YR",
        n_bins=2,
    )

    assert len(result) == 2
    assert round(result["weighted_observed_risk"].iloc[0], 4) == 0.5
    assert round(result["weighted_observed_risk"].iloc[1], 4) == 0.5


def test_weighted_net_benefit_matches_manual_value():
    from src.evaluate_stage7 import weighted_net_benefit

    y_true = pd.Series([1, 0, 1, 0])
    predicted_positive = pd.Series([1, 1, 0, 0])
    weights = pd.Series([1.0, 1.0, 1.0, 1.0])

    result = weighted_net_benefit(
        y_true,
        predicted_positive,
        weights,
        threshold=0.20,
    )

    expected = (1.0 - 1.0 * 0.25) / 4.0
    assert abs(result - expected) < 1e-12


def test_bootstrap_metric_intervals_are_ordered():
    from src.evaluate_stage7 import bootstrap_metric_intervals

    df = pd.DataFrame(
        {
            "undiagnosed_hypertension": [0, 1] * 30,
            "predicted_risk": [0.35, 0.65] * 30,
            "WTMEC2YR": [1.0] * 60,
        }
    )

    result = bootstrap_metric_intervals(
        df,
        target="undiagnosed_hypertension",
        probability="predicted_risk",
        weight="WTMEC2YR",
        n_bootstrap=50,
        random_seed=7,
    )

    assert {"weighted_roc_auc", "weighted_brier_score"}.issubset(
        result["metric"].tolist()
    )
    assert np.isfinite(result["estimate"]).all()
    assert np.isfinite(result["ci_lower"]).all()
    assert np.isfinite(result["ci_upper"]).all()
    assert (result["ci_lower"] <= result["ci_upper"]).all()
    assert (result["bootstrap_replicates_used"] > 0).all()