"""In-memory two-arm CV. No file loading, output saving or permission grants."""

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src.depression_execution_v1 import (
    check_contract,
    check_row_alignment,
)
from src.depression_baseline_fit_v1 import fit_reference
from src.depression_secondary_v1 import fit_secondary_reference


def run_two_arm_cv(config, X, y, weights, groups):
    check_contract(config)

    evaluation = config["evaluation"]
    expected = {
        "splitter": "StratifiedGroupKFold",
        "n_splits": 5,
        "shuffle": True,
        "random_state": 42,
        "group_fields": ["SDMVSTRA", "SDMVPSU"],
        "comparison_arms": ["primary", "age_gender"],
    }
    for key, value in expected.items():
        actual = evaluation.get(key)
        if actual != value or type(actual) is not type(value):
            raise PermissionError(f"Unexpected evaluation setting: {key}")

    check_row_alignment(X, y, weights)

    if not isinstance(groups, pd.Series):
        raise ValueError("Groups must be an indexed Series.")
    if not X.index.equals(groups.index):
        raise ValueError("Group index differs from predictor index.")
    if groups.isna().any():
        raise ValueError("Missing group identity.")

    group_codes, unique_groups = pd.factorize(groups, sort=False)
    if len(unique_groups) < 5:
        raise ValueError("Fewer than five distinct groups.")

    labels = y.to_numpy(dtype=float)
    if not np.isfinite(labels).all() or set(np.unique(labels)) != {0.0, 1.0}:
        raise ValueError("Expected both binary outcome classes.")

    splitter = StratifiedGroupKFold(
        n_splits=5, shuffle=True, random_state=42
    )

    # Materialize and validate every partition before any fitting.
    splits = list(splitter.split(np.zeros((len(X), 1)), labels, group_codes))
    if len(splits) != 5:
        raise ValueError("Unexpected number of folds.")

    coverage = np.zeros(len(X), dtype=int)
    for train, heldout in splits:
        train = np.asarray(train)
        heldout = np.asarray(heldout)
        for indices in (train, heldout):
            if (
                indices.ndim != 1
                or not np.issubdtype(indices.dtype, np.integer)
                or len(indices) == 0
                or len(np.unique(indices)) != len(indices)
                or (indices < 0).any()
                or (indices >= len(X)).any()
            ):
                raise ValueError("Invalid partition indices.")

        if np.intersect1d(train, heldout).size:
            raise ValueError("Participant overlap.")
        if np.union1d(train, heldout).size != len(X):
            raise ValueError("Partition does not cover the cohort.")
        if np.intersect1d(
            group_codes[train], group_codes[heldout]
        ).size:
            raise ValueError("Group overlap.")
        if (
            set(np.unique(labels[train])) != {0.0, 1.0}
            or set(np.unique(labels[heldout])) != {0.0, 1.0}
        ):
            raise ValueError("A partition lacks an outcome class.")
        if X.iloc[train]["INDFMPIR"].isna().all():
            raise ValueError("Training income is entirely missing.")

        coverage[heldout] += 1

    if not np.all(coverage == 1):
        raise ValueError("Held-out coverage is not exactly one.")

    predictions = {
        "primary": np.full(len(X), np.nan),
        "age_gender": np.full(len(X), np.nan),
    }
    summaries = []

    for fold, (train, heldout) in enumerate(splits, start=1):
        for arm, fields, fit_function in (
            (
                "primary",
                ["RIDAGEYR", "RIAGENDR", "INDFMPIR"],
                fit_reference,
            ),
            (
                "age_gender",
                ["RIDAGEYR", "RIAGENDR"],
                fit_secondary_reference,
            ),
        ):
            preprocessing, estimator = fit_function(
                X.iloc[train][fields],
                labels[train],
                weights.iloc[train].to_numpy(),
            )
            if not np.array_equal(estimator.classes_, [0, 1]):
                raise ValueError("Unexpected estimator class ordering.")

            probability = estimator.predict_proba(
                preprocessing.transform(X.iloc[heldout][fields])
            )
            if (
                probability.shape != (len(heldout), 2)
                or not np.isfinite(probability).all()
                or (probability < 0).any()
                or (probability > 1).any()
                or not np.allclose(probability.sum(axis=1), 1)
            ):
                raise ValueError("Invalid predicted probabilities.")

            predictions[arm][heldout] = probability[:, 1]

        summaries.append({
            "fold": fold,
            "training_rows": len(train),
            "heldout_rows": len(heldout),
            "training_groups": len(np.unique(group_codes[train])),
            "heldout_groups": len(np.unique(group_codes[heldout])),
        })

    result = pd.DataFrame(predictions, index=X.index.copy())
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError("Incomplete prediction output.")

    return result, summaries
