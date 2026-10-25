from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix


REPO_ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = (
    REPO_ROOT
    / "outputs"
    / "models"
    / "P6_STAGE7_hypertension_temporal_test_predictions.csv"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "models"
    / "P6_STAGE7_hypertension_temporal_test_threshold_audit.csv"
)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    return float(np.average(values.astype(float), weights=weights.astype(float)))


def main() -> None:
    df = pd.read_csv(PREDICTIONS_PATH)

    target = "undiagnosed_hypertension"
    probability = "predicted_risk"
    weight = "WTMEC2YR"

    rows = []
    for threshold in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
        predicted_positive = (df[probability] >= threshold).astype(int)

        tp = ((predicted_positive == 1) & (df[target] == 1))
        fn = ((predicted_positive == 0) & (df[target] == 1))
        tn = ((predicted_positive == 0) & (df[target] == 0))
        fp = ((predicted_positive == 1) & (df[target] == 0))

        weighted_tp = float(df.loc[tp, weight].sum())
        weighted_fn = float(df.loc[fn, weight].sum())
        weighted_tn = float(df.loc[tn, weight].sum())
        weighted_fp = float(df.loc[fp, weight].sum())

        sensitivity = weighted_tp / (weighted_tp + weighted_fn)
        specificity = weighted_tn / (weighted_tn + weighted_fp)
        ppv = weighted_tp / (weighted_tp + weighted_fp)
        npv = weighted_tn / (weighted_tn + weighted_fn)

        rows.append(
            {
                "threshold": threshold,
                "weighted_screen_positive_fraction": weighted_mean(
                    predicted_positive,
                    df[weight],
                ),
                "weighted_sensitivity": sensitivity,
                "weighted_specificity": specificity,
                "weighted_ppv": ppv,
                "weighted_npv": npv,
                "unweighted_tp": int(tp.sum()),
                "unweighted_fp": int(fp.sum()),
                "unweighted_tn": int(tn.sum()),
                "unweighted_fn": int(fn.sum()),
            }
        )

    audit = pd.DataFrame(rows)
    audit.to_csv(OUTPUT_PATH, index=False)

    print(OUTPUT_PATH)
    print(audit.round(4).to_string(index=False))


if __name__ == "__main__":
    main()