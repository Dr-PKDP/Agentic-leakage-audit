import pandas as pd


def test_split_temporal_data_keeps_final_cycle_untouched():
    from src.train_models_stage7 import split_temporal_data

    df = pd.DataFrame(
        {
            "SEQN": [1, 2, 3, 4],
            "nhanes_cycle": ["2011-2012", "2015-2016", "2021-2023", "2021-2023"],
            "undiagnosed_hypertension": [0, 1, 0, 1],
        }
    )

    development, test = split_temporal_data(
        df=df,
        development_cycles=["2011-2012", "2013-2014", "2015-2016"],
        final_test_cycle="2021-2023",
    )

    assert len(development) == 2
    assert len(test) == 2
    assert set(development["nhanes_cycle"]) == {"2011-2012", "2015-2016"}
    assert set(test["nhanes_cycle"]) == {"2021-2023"}


def test_get_predictor_columns_excludes_ids_target_and_survey_design():
    from src.train_models_stage7 import get_predictor_columns

    df = pd.DataFrame(
        {
            "SEQN": [1],
            "nhanes_cycle": ["2011-2012"],
            "undiagnosed_hypertension": [0],
            "WTMEC2YR": [1000.0],
            "SDMVSTRA": [1],
            "SDMVPSU": [1],
            "RIDAGEYR": [45],
            "ALQ130": [2],
        }
    )

    predictors = get_predictor_columns(
        df=df,
        id_columns=["SEQN", "nhanes_cycle"],
        target="undiagnosed_hypertension",
        target_exclusions=[
            "undiagnosed_hypertension",
            "WTMEC2YR",
            "SDMVSTRA",
            "SDMVPSU",
        ],
    )

    assert predictors == ["RIDAGEYR", "ALQ130"]


def test_weighted_brier_score_matches_manual_calculation():
    from src.train_models_stage7 import weighted_brier_score

    y_true = pd.Series([0, 1])
    probabilities = pd.Series([0.2, 0.8])
    weights = pd.Series([2.0, 1.0])

    result = weighted_brier_score(y_true, probabilities, weights)

    expected = (2.0 * 0.2**2 + 1.0 * (1.0 - 0.8)**2) / 3.0
    assert abs(result - expected) < 1e-12


def test_calibration_slope_is_finite_for_nonconstant_predictions():
    from src.train_models_stage7 import calibration_slope

    y_true = pd.Series([0, 0, 1, 1, 0, 1])
    probabilities = pd.Series([0.1, 0.2, 0.7, 0.8, 0.3, 0.9])
    weights = pd.Series([1.0] * 6)

    result = calibration_slope(y_true, probabilities, weights)

    assert result is not None
    assert result > 0