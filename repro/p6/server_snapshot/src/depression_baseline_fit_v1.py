"""Baseline fitting components. Real-data execution requires a separate gate."""

import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from src.depression_preprocessing_v1 import DepressionPreprocessor


def normalize_training_weights(weights, n):
    values = np.asarray(weights, dtype=float)
    if values.ndim != 1 or len(values) != n or n == 0:
        raise ValueError("Weights must be a nonempty aligned vector.")
    if not (np.isfinite(values).all() and (values > 0).all()):
        raise ValueError("Weights must be finite and positive.")

    mean = values.mean()
    if not np.isfinite(mean) or mean <= 0:
        raise ValueError("Invalid training weight mean.")

    normalized = values / mean
    if not (
        np.isfinite(normalized).all()
        and (normalized > 0).all()
    ):
        raise ValueError("Invalid normalized training weights.")
    return normalized


def fit_reference(X_train, y_train, training_weights):
    """Inputs are positional; callers must establish row alignment and permission."""
    y = np.asarray(y_train, dtype=float)
    if y.ndim != 1 or len(y) != len(X_train):
        raise ValueError("Labels must be aligned with training rows.")
    if not np.isfinite(y).all() or set(np.unique(y)) != {0.0, 1.0}:
        raise ValueError("Training labels must contain both binary classes.")

    weights = normalize_training_weights(training_weights, len(X_train))
    preprocessing = DepressionPreprocessor()
    transformed = preprocessing.fit_transform(X_train)

    estimator = LogisticRegression(
        solver="lbfgs",
        l1_ratio=0,
        C=1.0,
        fit_intercept=True,
        class_weight=None,
        max_iter=2000,
        tol=1e-6,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        estimator.fit(transformed, y, sample_weight=weights)

    return preprocessing, estimator
