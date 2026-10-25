import numpy as np
import pandas as pd


def test_split_stage8_data_uses_disjoint_cycles():
    from src.recalibrate_stage8 import split_stage8_data

    df = pd.DataFrame(
        {
            "nhanes_cycle": [
                "2011-2012",
                "2013-2014",
                "2015-2016",
                "2021-2023",
            ],
            "undiagnosed_hypertension": [0, 1, 0, 1],
        }
    )

    train, calibration, later = split_stage8_data(
        df,
        training_cycles=["2011-2012", "2013-2014"],
        calibration_cycle="2015-2016",
        later_cycle="2021-2023",
    )

    assert len(train) == 2
    assert len(calibration) == 1
    assert len(later) == 1
    assert set(train["nhanes_cycle"]) == {"2011-2012", "2013-2014"}
    assert set(calibration["nhanes_cycle"]) == {"2015-2016"}
    assert set(later["nhanes_cycle"]) == {"2021-2023"}


def test_platt_scaling_probabilities_are_valid():
    from src.recalibrate_stage8 import fit_platt_scaler

    raw_probabilities = np.array([0.15, 0.25, 0.60, 0.75])
    y = pd.Series([0, 0, 1, 1])
    weights = pd.Series([1.0, 2.0, 1.0, 1.0])

    scaler = fit_platt_scaler(raw_probabilities, y, weights)
    calibrated = scaler.predict_proba(raw_probabilities.reshape(-1, 1))[:, 1]

    assert np.all(calibrated >= 0)
    assert np.all(calibrated <= 1)
    assert calibrated[0] < calibrated[-1]


def test_apply_platt_scaler_preserves_row_count():
    from src.recalibrate_stage8 import apply_platt_scaler

    from sklearn.linear_model import LogisticRegression

    probabilities = np.array([0.20, 0.30, 0.70, 0.80])
    y = np.array([0, 0, 1, 1])

    scaler = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000)
    scaler.fit(probabilities.reshape(-1, 1), y)

    result = apply_platt_scaler(scaler, probabilities)

    assert len(result) == len(probabilities)
    assert np.all(result >= 0)
    assert np.all(result <= 1)