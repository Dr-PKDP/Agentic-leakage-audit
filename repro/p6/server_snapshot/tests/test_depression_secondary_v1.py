import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.depression_baseline_fit_v1 import fit_reference
from src.depression_secondary_v1 import (
    AgeGenderPreprocessor,
    fit_secondary_reference,
)


class SecondaryTests(unittest.TestCase):
    def setUp(self):
        self.X = pd.DataFrame({
            "RIDAGEYR": [20, 30, 40, 50, 60, 70, 80, 45],
            "RIAGENDR": [1, 2, 1, 2, 1, 2, 1, 2],
        })
        self.y = np.array([0, 1, 0, 1, 1, 0, 1, 0])
        self.w = np.arange(1, 9, dtype=float)

    def test_known_scaling_and_encoding(self):
        X = pd.DataFrame({
            "RIDAGEYR": [20, 40, 60, 80],
            "RIAGENDR": [1, 2, 1, 2],
        })
        pre = AgeGenderPreprocessor().fit(X)
        result = pre.transform(X)
        np.testing.assert_allclose(
            result[:, 0], (X["RIDAGEYR"] - 50) / np.sqrt(500)
        )
        np.testing.assert_array_equal(result[:, 1], [0, 1, 0, 1])
        self.assertEqual(result.shape, (4, 2))

    def test_income_or_outcome_columns_rejected(self):
        for name in ("INDFMPIR", "INDFMPIR_missing", "DPQ010"):
            with self.subTest(column=name):
                with self.assertRaises(ValueError):
                    AgeGenderPreprocessor().fit(self.X.assign(**{name: 0}))

    def test_invalid_inputs_rejected(self):
        for field, value in [
            ("RIDAGEYR", 40.5),
            ("RIDAGEYR", np.nan),
            ("RIAGENDR", 3),
            ("RIAGENDR", np.nan),
        ]:
            with self.subTest(field=field, value=value):
                X = self.X.astype(float).copy()
                X.loc[0, field] = value
                with self.assertRaises(ValueError):
                    AgeGenderPreprocessor().fit(X)

    def test_heldout_transform_does_not_mutate_statistics(self):
        pre = AgeGenderPreprocessor().fit(self.X)
        before_mean = pre.scaler_.mean_.copy()
        before_scale = pre.scaler_.scale_.copy()
        heldout = pd.DataFrame({
            "RIDAGEYR": [18, 80],
            "RIAGENDR": [2, 1],
        })
        result = pre.transform(heldout)
        self.assertTrue(np.isfinite(result).all())
        np.testing.assert_array_equal(pre.scaler_.mean_, before_mean)
        np.testing.assert_array_equal(pre.scaler_.scale_, before_scale)

    def test_weights_reach_secondary_estimator(self):
        with patch("src.depression_secondary_v1.LogisticRegression") as ctor:
            fit_secondary_reference(self.X, self.y, self.w)
            args, kwargs = ctor.return_value.fit.call_args
            self.assertEqual(args[0].shape, (8, 2))
            np.testing.assert_allclose(
                kwargs["sample_weight"], self.w / self.w.mean()
            )

    def test_synthetic_fit_matches_primary_estimator_settings(self):
        _, secondary = fit_secondary_reference(self.X, self.y, self.w)
        primary_X = self.X.assign(
            INDFMPIR=[1, 2, np.nan, 4, 2, 3, 5, np.nan]
        )
        _, primary = fit_reference(primary_X, self.y, self.w)
        self.assertEqual(primary.get_params(), secondary.get_params())

        pre, model = fit_secondary_reference(self.X, self.y, self.w)
        probabilities = model.predict_proba(pre.transform(self.X))
        self.assertEqual(probabilities.shape, (8, 2))
        self.assertTrue(np.isfinite(probabilities).all())
        self.assertTrue(
            ((probabilities >= 0) & (probabilities <= 1)).all()
        )
        np.testing.assert_allclose(probabilities.sum(axis=1), 1)
