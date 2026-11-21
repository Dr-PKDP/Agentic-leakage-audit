import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted


class DepressionPreprocessor(BaseEstimator, TransformerMixin):
    """Fixed primary-baseline transform; no estimator or data loading."""

    columns = ["RIDAGEYR", "RIAGENDR", "INDFMPIR"]

    def _validate(self, X):
        if not isinstance(X, pd.DataFrame):
            raise ValueError("Expected a pandas DataFrame.")
        if X.columns.duplicated().any():
            raise ValueError("Duplicate column names.")
        if set(X.columns) != set(self.columns):
            raise ValueError("Expected exactly the three approved input fields.")
        if len(X) == 0:
            raise ValueError("Empty input.")

        age = X["RIDAGEYR"].to_numpy(dtype=float)
        gender = X["RIAGENDR"].to_numpy(dtype=float)
        income = X["INDFMPIR"].to_numpy(dtype=float)

        if not (
            np.isfinite(age).all()
            and ((age >= 18) & (age <= 80)).all()
            and (age == np.floor(age)).all()
        ):
            raise ValueError("Invalid age.")

        if not (np.isfinite(gender).all()
                and np.isin(gender, [1, 2]).all()):
            raise ValueError("Invalid released gender code.")

        observed = income[~np.isnan(income)]
        if not (
            np.isfinite(observed).all()
            and ((observed >= 0) & (observed <= 5)).all()
        ):
            raise ValueError("Invalid income ratio.")

        return age, gender, income

    def fit(self, X, y=None):
        age, _, income = self._validate(X)
        if np.isnan(income).all():
            raise ValueError("All training income is missing.")

        self.income_median_ = float(np.nanmedian(income))
        filled = np.where(np.isnan(income), self.income_median_, income)
        self.scaler_ = StandardScaler().fit(
            np.column_stack([age, filled])
        )
        self.n_features_in_ = 3
        self.feature_names_in_ = np.asarray(self.columns, dtype=object)
        return self

    def transform(self, X):
        check_is_fitted(self, ["income_median_", "scaler_"])
        age, gender, income = self._validate(X)
        missing = np.isnan(income)
        filled = np.where(missing, self.income_median_, income)
        continuous = self.scaler_.transform(
            np.column_stack([age, filled])
        )
        return np.column_stack([
            continuous,
            gender - 1,
            missing.astype(float),
        ])

    def get_feature_names_out(self, input_features=None):
        return np.asarray([
            "age_scaled",
            "income_scaled",
            "released_gender_code_2",
            "INDFMPIR_missing",
        ], dtype=object)
