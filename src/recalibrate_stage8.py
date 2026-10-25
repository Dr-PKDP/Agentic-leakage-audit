from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "configs" / "stage8_hypertension_recalibration_protocol.yaml"


def load_protocol() -> dict:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def split_stage8_data(
    df: pd.DataFrame,
    training_cycles: list[str],
    calibration_cycle: str,
    later_cycle: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df.loc[df["nhanes_cycle"].isin(training_cycles)].copy()
    calibration = df.loc[df["nhanes_cycle"].eq(calibration_cycle)].copy()
    later = df.loc[df["nhanes_cycle"].eq(later_cycle)].copy()
    return train, calibration, later


def get_predictors(df: pd.DataFrame, protocol: dict) -> list[str]:
    excluded = set(
        protocol["id_columns"]
        + protocol["excluded_from_predictors"]
    )
    return [column for column in df.columns if column not in excluded]


def get_column_types(
    df: pd.DataFrame,
    predictors: list[str],
) -> tuple[list[str], list[str]]:
    numeric = [
        column
        for column in predictors
        if pd.api.types.is_numeric_dtype(df[column])
    ]
    categorical = [column for column in predictors if column not in numeric]
    return numeric, categorical


def make_random_forest_pipeline(
    numeric: list[str],
    categorical: list[str],
    protocol: dict,
) -> Pipeline:
    preprocessor = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [("imputer", SimpleImputer(strategy="median"))]
                ),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
    )

    settings = protocol["base_model"]
    model = RandomForestClassifier(
        n_estimators=settings["n_estimators"],
        min_samples_leaf=settings["min_samples_leaf"],
        class_weight=settings["class_weight"],
        n_jobs=-1,
        random_state=settings["random_seed"],
    )

    return Pipeline(
        [
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def fit_platt_scaler(
    raw_probabilities: np.ndarray,
    y_true: pd.Series | np.ndarray,
    weights: pd.Series | np.ndarray,
) -> LogisticRegression:
    raw = np.asarray(raw_probabilities, dtype=float)
    raw = np.clip(raw, 1e-6, 1 - 1e-6)

    scaler = LogisticRegression(
        C=np.inf,
        solver="lbfgs",
        max_iter=1000,
    )
    scaler.fit(
        raw.reshape(-1, 1),
        np.asarray(y_true, dtype=int),
        sample_weight=np.asarray(weights, dtype=float),
    )
    return scaler


def apply_platt_scaler(
    scaler: LogisticRegression,
    raw_probabilities: np.ndarray,
) -> np.ndarray:
    raw = np.asarray(raw_probabilities, dtype=float)
    raw = np.clip(raw, 1e-6, 1 - 1e-6)
    return scaler.predict_proba(raw.reshape(-1, 1))[:, 1]


def calibration_parameters(
    y_true: pd.Series,
    probabilities: np.ndarray,
    weights: pd.Series,
) -> tuple[float, float]:
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))

    model = LogisticRegression(
        C=np.inf,
        solver="lbfgs",
        max_iter=1000,
    )
    model.fit(
        logit.reshape(-1, 1),
        np.asarray(y_true, dtype=int),
        sample_weight=np.asarray(weights, dtype=float),
    )

    return float(model.coef_[0, 0]), float(model.intercept_[0])


def evaluate(
    y_true: pd.Series,
    probabilities: np.ndarray,
    weights: pd.Series,
) -> dict[str, float]:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    w = np.asarray(weights, dtype=float)

    slope, intercept = calibration_parameters(y, p, w)

    return {
        "weighted_roc_auc": float(roc_auc_score(y, p, sample_weight=w)),
        "weighted_average_precision": float(
            average_precision_score(y, p, sample_weight=w)
        ),
        "weighted_brier_score": float(np.average((y - p) ** 2, weights=w)),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
    }


def make_prediction_frame(
    frame: pd.DataFrame,
    raw_probability: np.ndarray,
    calibrated_probability: np.ndarray,
    target: str,
    weight: str,
) -> pd.DataFrame:
    result = frame[["SEQN", "nhanes_cycle", target, weight]].copy()
    result["raw_predicted_risk"] = raw_probability
    result["platt_calibrated_risk"] = calibrated_probability
    return result


def main() -> None:
    protocol = load_protocol()

    feature_path = (
        REPO_ROOT
        / protocol["feature_dir"]
        / protocol["feature_file"]
    )
    output_dir = REPO_ROOT / protocol["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(feature_path)
    train, calibration, later = split_stage8_data(
        df,
        training_cycles=protocol["training_cycles"],
        calibration_cycle=protocol["calibration_cycle"],
        later_cycle=protocol[
            "previously_accessed_temporal_evaluation_cycle"
        ],
    )

    target = protocol["target"]
    weight = protocol["survey_design"]["weight"]
    predictors = get_predictors(df, protocol)
    numeric, categorical = get_column_types(train, predictors)

    pipeline = make_random_forest_pipeline(
        numeric,
        categorical,
        protocol,
    )
    pipeline.fit(
        train[predictors],
        train[target],
        model__sample_weight=train[weight],
    )

    raw_calibration = pipeline.predict_proba(
        calibration[predictors]
    )[:, 1]

    scaler = fit_platt_scaler(
        raw_calibration,
        calibration[target],
        calibration[weight],
    )
    calibrated_calibration = apply_platt_scaler(
        scaler,
        raw_calibration,
    )

    raw_later = pipeline.predict_proba(later[predictors])[:, 1]
    calibrated_later = apply_platt_scaler(scaler, raw_later)

    calibration_predictions = make_prediction_frame(
        calibration,
        raw_calibration,
        calibrated_calibration,
        target,
        weight,
    )
    later_predictions = make_prediction_frame(
        later,
        raw_later,
        calibrated_later,
        target,
        weight,
    )

    calibration_predictions_path = (
        output_dir
        / "P6_STAGE8_hypertension_2015_2016_calibration_predictions.csv"
    )
    later_predictions_path = (
        output_dir
        / "P6_STAGE8_hypertension_2021_2023_descriptive_predictions.csv"
    )
    calibration_predictions.to_csv(calibration_predictions_path, index=False)
    later_predictions.to_csv(later_predictions_path, index=False)

    summary = {
        "training_cycles": protocol["training_cycles"],
        "calibration_cycle": protocol["calibration_cycle"],
        "later_cycle_label": (
            protocol["previously_accessed_temporal_evaluation_cycle"]
        ),
        "later_cycle_role": "descriptive_only_previously_accessed",
        "predictor_count": len(predictors),
        "training_rows": len(train),
        "calibration_rows": len(calibration),
        "calibration_raw_metrics": evaluate(
            calibration[target],
            raw_calibration,
            calibration[weight],
        ),
        "calibration_platt_metrics": evaluate(
            calibration[target],
            calibrated_calibration,
            calibration[weight],
        ),
        "later_descriptive_raw_metrics": evaluate(
            later[target],
            raw_later,
            later[weight],
        ),
        "later_descriptive_platt_metrics": evaluate(
            later[target],
            calibrated_later,
            later[weight],
        ),
    }

    summary_path = (
        output_dir / "P6_STAGE8_hypertension_recalibration_summary.json"
    )
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(calibration_predictions_path)
    print(later_predictions_path)
    print(summary_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()