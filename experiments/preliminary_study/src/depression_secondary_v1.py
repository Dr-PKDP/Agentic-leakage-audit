"""Age/gender secondary arm. Real-data execution is not authorized here."""

import warnings

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

from src.depression_baseline_fit_v1 import normalize_training_weights


class AgeGenderPreprocessor(BaseEstimator, TransformerMixin):
    columns = ["RIDAGEYR", "RIAGENDR"]

    def _validate(self, X):
        if not isinstance(X, pd.DataFrame):
            raise ValueError("Expected a DataFrame.")
        if X.columns.duplicated().any() or list(X.columns) != self.columns:
            raise ValueError("Expected age and gender only, in fixed order.")
        if len(X) == 0:
            raise ValueError("Empty input.")

        age = X["RIDAGEYR"].to_numpy(dtype=float)
        gender = X["RIAGENDR"].to_numpy(dtype=float)

        if not (
            np.isfinite(age).all()
            and ((age >= 18) & (age <= 80)).all()
            and (age == np.floor(age)).all()
        ):
            raise ValueError("Invalid age.")
        if not (
            np.isfinite(gender).all()
            and np.isin(gender, [1, 2]).all()
        ):
            raise ValueError("Invalid released gender code.")
        return age, gender

    def fit(self, X, y=None):
        age, _ = self._validate(X)
        self.scaler_ = StandardScaler().fit(age.reshape(-1, 1))
        self.n_features_in_ = 2
        self.feature_names_in_ = np.asarray(self.columns, dtype=object)
        return self

    def transform(self, X):
        check_is_fitted(self, "scaler_")
        age, gender = self._validate(X)
        return np.column_stack([
            self.scaler_.transform(age.reshape(-1, 1)).ravel(),
            gender - 1,
        ])

    def get_feature_names_out(self, input_features=None):
        return np.asarray([
            "age_scaled",
            "released_gender_code_2",
        ], dtype=object)


def fit_secondary_reference(X_train, y_train, training_weights):
    """Positional helper; caller must enforce alignment and permissions."""
    y = np.asarray(y_train, dtype=float)
    if y.ndim != 1 or len(y) != len(X_train):
        raise ValueError("Misaligned labels.")
    if not np.isfinite(y).all() or set(np.unique(y)) != {0.0, 1.0}:
        raise ValueError("Training labels must contain both binary classes.")

    weights = normalize_training_weights(training_weights, len(X_train))
    preprocessing = AgeGenderPreprocessor()
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
