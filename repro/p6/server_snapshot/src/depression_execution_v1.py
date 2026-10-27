"""Guarded fitting entry point; does not load data or grant permissions."""

import pandas as pd

from src.depression_baseline_fit_v1 import (
    fit_reference,
    normalize_training_weights,
)


EXPECTED_FIELDS = ["RIDAGEYR", "RIAGENDR", "INDFMPIR"]


def check_contract(config):
    permissions = config.get("execution_permissions", {})
    if permissions.get("model_training") is not True:
        raise PermissionError("Model training is not explicitly permitted.")
    if permissions.get("local_baseline_fit") is not True:
        raise PermissionError("This baseline execution is not permitted.")

    policy = config.get("predictor_policy", {})
    if policy.get("status") != "approved_development_specification":
        raise PermissionError("Predictor specification is not approved.")
    if policy.get("candidate_allowlist") != EXPECTED_FIELDS:
        raise PermissionError("Predictor list differs from this implementation.")

    evaluation = config.get("evaluation", {})
    if evaluation.get("status") != "approved_development_evaluation":
        raise PermissionError("Development evaluation is not approved.")

    estimator = config.get("estimator_specification", {})
    if estimator.get("id") != "depression_logistic_baseline_v0.1":
        raise PermissionError("Unexpected estimator specification.")
    if estimator.get("implementation") != "primary_three_field_v1":
        raise PermissionError("Unsupported implementation arm.")


def check_row_alignment(X, y, weights):
    if not isinstance(X, pd.DataFrame):
        raise ValueError("Predictors must be a DataFrame.")
    if not isinstance(y, pd.Series) or not isinstance(weights, pd.Series):
        raise ValueError("Labels and weights must be indexed Series.")
    if len(X) == 0:
        raise ValueError("Empty training partition.")

    for index in (X.index, y.index, weights.index):
        if isinstance(index, pd.MultiIndex):
            raise ValueError("This implementation requires a single-level index.")
        if index.has_duplicates or index.isna().any():
            raise ValueError("Row indexes must be unique and nonmissing.")

    if not X.index.equals(y.index) or not X.index.equals(weights.index):
        raise ValueError("Predictor, label and weight indexes differ.")

    if X.columns.duplicated().any() or list(X.columns) != EXPECTED_FIELDS:
        raise ValueError("Unexpected predictor columns or column order.")

    normalize_training_weights(weights.to_numpy(), len(X))


def fit_authorized_reference(config, X, y, weights):
    check_contract(config)
    check_row_alignment(X, y, weights)
    return fit_reference(X, y.to_numpy(), weights.to_numpy())
