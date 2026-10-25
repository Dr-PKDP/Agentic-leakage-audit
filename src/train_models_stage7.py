from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "configs" / "stage7_hypertension_modeling_protocol.yaml"


def load_protocol() -> dict:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def split_temporal_data(
    df: pd.DataFrame,
    development_cycles: list[str],
    final_test_cycle: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    development = df.loc[
        df["nhanes_cycle"].isin(development_cycles)
    ].copy()
    test = df.loc[df["nhanes_cycle"] == final_test_cycle].copy()
    return development, test


def get_predictor_columns(
    df: pd.DataFrame,
    id_columns: list[str],
    target: str,
    target_exclusions: list[str],
) -> list[str]:
    excluded = set(id_columns + [target] + target_exclusions)
    return [column for column in df.columns if column not in excluded]


def weighted_brier_score(
    y_true: pd.Series,
    probabilities: pd.Series | np.ndarray,
    weights: pd.Series | np.ndarray,
) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probabilities, dtype=float)
    w = np.asarray(weights, dtype=float)
    return float(np.average((y - p) ** 2, weights=w))


def calibration_slope(
    y_true: pd.Series,
    probabilities: pd.Series | np.ndarray,
    weights: pd.Series | np.ndarray,
) -> float | None:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    w = np.asarray(weights, dtype=float)

    epsilon = 1e-6
    p = np.clip(p, epsilon, 1 - epsilon)
    logit_p = np.log(p / (1 - p))

    if len(np.unique(y)) < 2 or np.std(logit_p) == 0:
        return None

    model = LogisticRegression(
    C=np.inf,
    solver="lbfgs",
    max_iter=1000,
    )
    model.fit(logit_p.reshape(-1, 1), y, sample_weight=w)
    return float(model.coef_[0, 0])


def get_column_types(
    df: pd.DataFrame,
    predictor_columns: list[str],
) -> tuple[list[str], list[str]]:
    numeric_columns = [
        column
        for column in predictor_columns
        if pd.api.types.is_numeric_dtype(df[column])
    ]
    categorical_columns = [
        column
        for column in predictor_columns
        if column not in numeric_columns
    ]
    return numeric_columns, categorical_columns


def make_preprocessor(
    numeric_columns: list[str],
    categorical_columns: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    numeric_pipeline = Pipeline(numeric_steps)
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, numeric_columns),
            ("categorical", categorical_pipeline, categorical_columns),
        ],
        remainder="drop",
    )


def make_models(
    numeric_columns: list[str],
    categorical_columns: list[str],
    random_seed: int,
) -> dict[str, Pipeline]:
    linear_preprocessor = make_preprocessor(
        numeric_columns,
        categorical_columns,
        scale_numeric=True,
    )
    tree_preprocessor = make_preprocessor(
        numeric_columns,
        categorical_columns,
        scale_numeric=False,
    )

    return {
        "logistic_regression": Pipeline(
            [
                ("preprocessor", linear_preprocessor),
                (
                    "model",
                    LogisticRegression(
                        C=1.0,
    			l1_ratio=0.0,
  			class_weight="balanced",
    			solver="liblinear",
    			max_iter=2000,
    			random_state=random_seed,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocessor", tree_preprocessor),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=500,
                        min_samples_leaf=10,
                        class_weight="balanced",
                        n_jobs=-1,
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            [
                ("preprocessor", tree_preprocessor),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        learning_rate=0.05,
                        max_iter=300,
                        max_leaf_nodes=31,
                        l2_regularization=1.0,
                        random_state=random_seed,
                    ),
                ),
            ]
        ),
    }


def evaluate_predictions(
    y_true: pd.Series,
    probabilities: np.ndarray,
    weights: pd.Series,
) -> dict[str, float | None]:
    return {
        "weighted_roc_auc": float(
            roc_auc_score(y_true, probabilities, sample_weight=weights)
        ),
        "weighted_average_precision": float(
            average_precision_score(y_true, probabilities, sample_weight=weights)
        ),
        "weighted_brier_score": weighted_brier_score(
            y_true,
            probabilities,
            weights,
        ),
        "calibration_slope": calibration_slope(
            y_true,
            probabilities,
            weights,
        ),
    }


def cross_validate_models(
    development: pd.DataFrame,
    predictors: list[str],
    protocol: dict,
) -> pd.DataFrame:
    target = protocol["target"]
    weight_column = protocol["survey_design"]["weight"]
    seed = protocol["cross_validation"]["random_seed"]
    folds = protocol["cross_validation"]["folds"]

    numeric_columns, categorical_columns = get_column_types(
        development,
        predictors,
    )
    models = make_models(numeric_columns, categorical_columns, seed)

    splitter = StratifiedKFold(
        n_splits=folds,
        shuffle=True,
        random_state=seed,
    )

    rows = []
    x = development[predictors]
    y = development[target]
    weights = development[weight_column]

    for model_name, pipeline in models.items():
        for fold, (train_index, valid_index) in enumerate(
            splitter.split(x, y),
            start=1,
        ):
            x_train = x.iloc[train_index]
            x_valid = x.iloc[valid_index]
            y_train = y.iloc[train_index]
            y_valid = y.iloc[valid_index]
            train_weights = weights.iloc[train_index]
            valid_weights = weights.iloc[valid_index]

            pipeline.fit(
                x_train,
                y_train,
                model__sample_weight=train_weights,
            )
            probabilities = pipeline.predict_proba(x_valid)[:, 1]
            metrics = evaluate_predictions(
                y_valid,
                probabilities,
                valid_weights,
            )

            rows.append(
                {
                    "model": model_name,
                    "fold": fold,
                    **metrics,
                }
            )

    return pd.DataFrame(rows)


def choose_model(cv_results: pd.DataFrame) -> str:
    summary = (
        cv_results.groupby("model", as_index=False)
        .agg(
            weighted_roc_auc_cv_mean=("weighted_roc_auc", "mean"),
            weighted_brier_score_cv_mean=("weighted_brier_score", "mean"),
            calibration_slope_cv_mean=("calibration_slope", "mean"),
        )
    )
    summary["calibration_slope_distance_from_one"] = (
        summary["calibration_slope_cv_mean"] - 1.0
    ).abs()

    summary = summary.sort_values(
        [
            "weighted_roc_auc_cv_mean",
            "weighted_brier_score_cv_mean",
            "calibration_slope_distance_from_one",
        ],
        ascending=[False, True, True],
    )
    return str(summary.iloc[0]["model"])


def evaluate_final_test(
    development: pd.DataFrame,
    test: pd.DataFrame,
    predictors: list[str],
    protocol: dict,
    model_name: str,
) -> tuple[dict[str, float | None], Pipeline, np.ndarray]:
    target = protocol["target"]
    weight_column = protocol["survey_design"]["weight"]
    seed = protocol["cross_validation"]["random_seed"]

    numeric_columns, categorical_columns = get_column_types(
        development,
        predictors,
    )
    models = make_models(numeric_columns, categorical_columns, seed)
    pipeline = models[model_name]

    pipeline.fit(
        development[predictors],
        development[target],
        model__sample_weight=development[weight_column],
    )
    probabilities = pipeline.predict_proba(test[predictors])[:, 1]

    metrics = evaluate_predictions(
        test[target],
        probabilities,
        test[weight_column],
    )
    return metrics, pipeline, probabilities


def main() -> None:
    protocol = load_protocol()
    feature_dir = REPO_ROOT / protocol["data_paths"]["feature_dir"]
    output_dir = REPO_ROOT / protocol["data_paths"]["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_file = protocol["feature_sets"]["primary"]
    df = pd.read_csv(feature_dir / feature_file)

    development, test = split_temporal_data(
        df,
        protocol["temporal_split"]["development_cycles"],
        protocol["temporal_split"]["final_test_cycle"],
    )

    predictors = get_predictor_columns(
        df,
        protocol["id_columns"],
        protocol["target"],
        protocol["target_exclusions"],
    )

    cv_results = cross_validate_models(development, predictors, protocol)
    cv_path = output_dir / "P6_STAGE7_hypertension_cv_results.csv"
    cv_results.to_csv(cv_path, index=False)

    selected_model = choose_model(cv_results)

    test_metrics, _, test_probabilities = evaluate_final_test(
        development,
        test,
        predictors,
        protocol,
        selected_model,
    )

    model_summary = {
        "feature_set": "minimal",
        "selected_model": selected_model,
        "development_rows": int(len(development)),
        "final_test_rows": int(len(test)),
        "predictor_count": int(len(predictors)),
        "test_metrics": test_metrics,
    }
    summary_path = output_dir / "P6_STAGE7_hypertension_model_summary.json"
    summary_path.write_text(
        json.dumps(model_summary, indent=2),
        encoding="utf-8",
    )

    predictions = test[
        ["SEQN", "nhanes_cycle", protocol["target"], protocol["survey_design"]["weight"]]
    ].copy()
    predictions["predicted_risk"] = test_probabilities
    predictions_path = output_dir / "P6_STAGE7_hypertension_temporal_test_predictions.csv"
    predictions.to_csv(predictions_path, index=False)

    print(cv_path)
    print(summary_path)
    print(predictions_path)
    print(json.dumps(model_summary, indent=2))


if __name__ == "__main__":
    main()