from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score


REPO_ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = (
    REPO_ROOT
    / "outputs"
    / "models"
    / "P6_STAGE7_hypertension_temporal_test_predictions.csv"
)
OUTPUT_DIR = REPO_ROOT / "outputs" / "models"

TARGET = "undiagnosed_hypertension"
PROBABILITY = "predicted_risk"
WEIGHT = "WTMEC2YR"
RANDOM_SEED = 20261023
N_BINS = 10
N_BOOTSTRAP = 1000


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    return float(
        np.average(
            np.asarray(values, dtype=float),
            weights=np.asarray(weights, dtype=float),
        )
    )


def weighted_quantile_bins(
    probabilities: pd.Series,
    weights: pd.Series,
    n_bins: int,
) -> pd.Series:
    frame = pd.DataFrame(
        {
            "probability": pd.to_numeric(probabilities, errors="coerce"),
            "weight": pd.to_numeric(weights, errors="coerce"),
        }
    ).dropna()

    result = pd.Series(pd.NA, index=probabilities.index, dtype="Int64")

    if frame.empty:
        return result

    frame = frame.sort_values("probability", kind="stable").copy()
    total_weight = frame["weight"].sum()

    if total_weight <= 0:
        raise ValueError("Weights must sum to a positive value.")

    frame["weight_before"] = frame["weight"].cumsum() - frame["weight"]
    frame["weighted_midpoint_rank"] = (
        (frame["weight_before"] + 0.5 * frame["weight"]) / total_weight
    )

    frame["bin"] = np.minimum(
        (frame["weighted_midpoint_rank"] * n_bins).astype(int),
        n_bins - 1,
    )

    result.loc[frame.index] = frame["bin"].astype("Int64")
    return result


def weighted_calibration_table(
    df: pd.DataFrame,
    target: str,
    probability: str,
    weight: str,
    n_bins: int = 10,
) -> pd.DataFrame:
    work = df[[target, probability, weight]].dropna().copy()
    work["bin"] = weighted_quantile_bins(
        work[probability],
        work[weight],
        n_bins,
    )

    rows = []
    for bin_id, group in work.groupby("bin", observed=True):
        rows.append(
            {
                "bin": int(bin_id),
                "n_unweighted": int(len(group)),
                "weight_sum": float(group[weight].sum()),
                "weighted_mean_predicted_risk": weighted_mean(
                    group[probability],
                    group[weight],
                ),
                "weighted_observed_risk": weighted_mean(
                    group[target],
                    group[weight],
                ),
            }
        )

    return pd.DataFrame(rows).sort_values("bin").reset_index(drop=True)


def weighted_net_benefit(
    y_true: pd.Series,
    predicted_positive: pd.Series,
    weights: pd.Series,
    threshold: float,
) -> float:
    y = np.asarray(y_true, dtype=int)
    positive = np.asarray(predicted_positive, dtype=int)
    w = np.asarray(weights, dtype=float)

    true_positive_weight = w[(y == 1) & (positive == 1)].sum()
    false_positive_weight = w[(y == 0) & (positive == 1)].sum()
    total_weight = w.sum()

    threshold_odds = threshold / (1 - threshold)
    return float(
        (true_positive_weight - false_positive_weight * threshold_odds)
        / total_weight
    )


def weighted_metrics(
    df: pd.DataFrame,
    target: str,
    probability: str,
    weight: str,
) -> dict[str, float]:
    y = df[target]
    p = df[probability]
    w = df[weight]

    epsilon = 1e-6
    p_clipped = np.clip(np.asarray(p, dtype=float), epsilon, 1 - epsilon)
    logit_p = np.log(p_clipped / (1 - p_clipped))

    calibration_model = LogisticRegression(
        C=np.inf,
        solver="lbfgs",
        max_iter=1000,
    )
    calibration_model.fit(
        logit_p.reshape(-1, 1),
        y,
        sample_weight=w,
    )

    return {
        "weighted_roc_auc": float(roc_auc_score(y, p, sample_weight=w)),
        "weighted_average_precision": float(
            average_precision_score(y, p, sample_weight=w)
        ),
        "weighted_brier_score": float(
            np.average((np.asarray(y) - np.asarray(p)) ** 2, weights=w)
        ),
        "calibration_slope": float(calibration_model.coef_[0, 0]),
        "calibration_intercept": float(calibration_model.intercept_[0]),
    }


def bootstrap_metric_intervals(
    df: pd.DataFrame,
    target: str,
    probability: str,
    weight: str,
    n_bootstrap: int,
    random_seed: int,
) -> pd.DataFrame:
    metrics = weighted_metrics(df, target, probability, weight)
    rng = np.random.default_rng(random_seed)
    bootstrap_values: dict[str, list[float]] = {
        name: [] for name in metrics
    }

    for _ in range(n_bootstrap):
        indices = rng.integers(0, len(df), size=len(df))
        sample = df.iloc[indices]

        if sample[target].nunique() < 2:
            continue

        values = weighted_metrics(sample, target, probability, weight)
        for name, value in values.items():
            bootstrap_values[name].append(value)

    rows = []
    for name, estimate in metrics.items():
        distribution = np.asarray(bootstrap_values[name], dtype=float)
        rows.append(
            {
                "metric": name,
                "estimate": estimate,
                "ci_lower": float(np.quantile(distribution, 0.025)),
                "ci_upper": float(np.quantile(distribution, 0.975)),
                "bootstrap_replicates_used": int(len(distribution)),
                "bootstrap_method": "person_resampled_exploratory",
            }
        )

    return pd.DataFrame(rows)


def decision_curve_table(
    df: pd.DataFrame,
    target: str,
    probability: str,
    weight: str,
) -> pd.DataFrame:
    y = df[target]
    w = df[weight]
    prevalence = weighted_mean(y, w)

    rows = []
    for threshold in np.arange(0.10, 0.51, 0.01):
        predicted_positive = (df[probability] >= threshold).astype(int)

        model_net_benefit = weighted_net_benefit(
            y,
            predicted_positive,
            w,
            float(threshold),
        )
        treat_all_net_benefit = prevalence - (
            (1 - prevalence) * threshold / (1 - threshold)
        )

        rows.append(
            {
                "threshold": round(float(threshold), 2),
                "model_net_benefit": model_net_benefit,
                "screen_all_net_benefit": treat_all_net_benefit,
                "screen_none_net_benefit": 0.0,
                "model_minus_screen_all": (
                    model_net_benefit - treat_all_net_benefit
                ),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(PREDICTIONS_PATH)

    calibration = weighted_calibration_table(
        predictions,
        TARGET,
        PROBABILITY,
        WEIGHT,
        n_bins=N_BINS,
    )
    calibration_path = (
        OUTPUT_DIR
        / "P6_STAGE7_hypertension_temporal_test_calibration.csv"
    )
    calibration.to_csv(calibration_path, index=False)

    decision_curve = decision_curve_table(
        predictions,
        TARGET,
        PROBABILITY,
        WEIGHT,
    )
    decision_curve_path = (
        OUTPUT_DIR
        / "P6_STAGE7_hypertension_temporal_test_decision_curve.csv"
    )
    decision_curve.to_csv(decision_curve_path, index=False)

    intervals = bootstrap_metric_intervals(
        predictions,
        TARGET,
        PROBABILITY,
        WEIGHT,
        n_bootstrap=N_BOOTSTRAP,
        random_seed=RANDOM_SEED,
    )
    intervals_path = (
        OUTPUT_DIR
        / "P6_STAGE7_hypertension_temporal_test_metric_ci.csv"
    )
    intervals.to_csv(intervals_path, index=False)

    print(calibration_path)
    print(decision_curve_path)
    print(intervals_path)
    print("\nCalibration:")
    print(calibration.round(4).to_string(index=False))
    print("\nMetric intervals:")
    print(intervals.round(4).to_string(index=False))
    print("\nDecision curve, first 10 rows:")
    print(decision_curve.head(10).round(5).to_string(index=False))


if __name__ == "__main__":
    main()