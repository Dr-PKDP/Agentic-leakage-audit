import numpy as np
import pandas as pd


def test_prepare_data_excludes_target_from_test_features():
    from src.stage9_pretest_runner import prepare_data

    df = pd.DataFrame(
        {
            "SEQN": [1001, 1002],
	    "nhanes_cycle": ["2011-2012", "2021-2023"],
            "undiagnosed_hypertension": [0, 1],
            "WTMEC2YR": [1.0, 2.0],
            "RIDAGEYR": [40, 50],
            "RIAGENDR": [1, 2],
        }
    )

    proposal = {
        "predictors": ["RIDAGEYR", "RIAGENDR"],
        "target": "undiagnosed_hypertension",
        "training_cycles": ["2011-2012"],
        "evaluation_cycle": "2021-2023",
    }

    X_train, y_train, w_train, X_test, test_ids = prepare_data(
        df,
        proposal,
    )

    assert list(X_train.columns) == ["RIDAGEYR", "RIAGENDR"]
    assert list(X_test.columns) == ["RIDAGEYR", "RIAGENDR"]
    assert "undiagnosed_hypertension" not in X_test.columns
    assert len(y_train) == 1
    assert len(w_train) == 1
    assert len(test_ids) == 1


def test_prediction_frame_has_no_target_column():
    from src.stage9_pretest_runner import make_prediction_frame

    test_ids = pd.DataFrame(
        {
            "SEQN": [1, 2],
            "nhanes_cycle": ["2021-2023", "2021-2023"],
        }
    )
    prediction = np.array([0.2, 0.8])

    result = make_prediction_frame(test_ids, prediction)

    assert list(result.columns) == [
        "SEQN",
        "nhanes_cycle",
        "predicted_risk",
    ]
    assert "undiagnosed_hypertension" not in result.columns
    assert len(result) == 2


def test_make_model_supports_random_forest():
    from src.stage9_pretest_runner import make_model

    proposal = {
        "model": {
            "name": "random_forest",
            "n_estimators": 10,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
            "random_state": 7,
        }
    }

    model = make_model(proposal)

    assert model.n_estimators == 10
    assert model.min_samples_leaf == 2
    assert model.random_state == 7