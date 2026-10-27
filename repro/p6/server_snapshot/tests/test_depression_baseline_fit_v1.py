import unittest
import warnings
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from src.depression_baseline_fit_v1 import (
    fit_reference,
    normalize_training_weights,
)


class BaselineFitTests(unittest.TestCase):
    def setUp(self):
        self.X = pd.DataFrame({
            "RIDAGEYR": [20, 30, 40, 50, 60, 70, 80, 45],
            "RIAGENDR": [1, 2, 1, 2, 1, 2, 1, 2],
            "INDFMPIR": [1, 2, np.nan, 4, 2, 3, 5, np.nan],
        })
        self.y = np.array([0, 1, 0, 1, 1, 0, 1, 0])
        self.w = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=float)

    def test_known_normalization_and_input_unchanged(self):
        original = self.w.copy()
        result = normalize_training_weights(self.w, len(self.w))
        np.testing.assert_allclose(result, original / 4.5)
        self.assertAlmostEqual(result.mean(), 1.0)
        np.testing.assert_array_equal(self.w, original)

    def test_constant_rescaling_preserves_normalized_weights(self):
        a = normalize_training_weights(self.w, len(self.w))
        b = normalize_training_weights(self.w * 1000, len(self.w))
        np.testing.assert_allclose(a, b)

    def test_invalid_weights_stop(self):
        cases = [
            [],
            [1, 2],
            np.ones((8, 1)),
            [0] + [1] * 7,
            [-1] + [1] * 7,
            [np.nan] + [1] * 7,
            [np.inf] + [1] * 7,
        ]
        for values in cases:
            with self.subTest(values=str(values)):
                with self.assertRaises(ValueError):
                    normalize_training_weights(values, len(self.X))

    def test_invalid_labels_stop(self):
        cases = [
            np.zeros(8),
            np.ones(8),
            np.array([2] + [0] * 7),
            np.array([np.nan] + [0] * 7),
            np.array([0, 1]),
        ]
        for values in cases:
            with self.subTest(values=str(values)):
                with self.assertRaises(ValueError):
                    fit_reference(self.X, values, self.w)

    def test_normalized_weights_reach_estimator(self):
        with patch(
            "src.depression_baseline_fit_v1.LogisticRegression"
        ) as constructor:
            fit_reference(self.X, self.y, self.w)
            args, kwargs = constructor.return_value.fit.call_args
            self.assertEqual(args[0].shape, (8, 4))
            np.testing.assert_array_equal(args[1], self.y)
            np.testing.assert_allclose(
                kwargs["sample_weight"], self.w / self.w.mean()
            )
            self.assertIsNone(constructor.call_args.kwargs["class_weight"])
            self.assertEqual(constructor.call_args.kwargs["C"], 1.0)

    def test_convergence_warning_stops(self):
        def warn_on_fit(*args, **kwargs):
            warnings.warn("Synthetic convergence fixture", ConvergenceWarning)

        with patch(
            "src.depression_baseline_fit_v1.LogisticRegression"
        ) as constructor:
            constructor.return_value.fit.side_effect = warn_on_fit
            with self.assertRaises(ConvergenceWarning):
                fit_reference(self.X, self.y, self.w)

    def test_real_synthetic_fit_and_probability_output(self):
        preprocessing, estimator = fit_reference(self.X, self.y, self.w)
        heldout = pd.DataFrame({
            "RIDAGEYR": [25, 65],
            "RIAGENDR": [1, 2],
            "INDFMPIR": [np.nan, 4.0],
        })
        probabilities = estimator.predict_proba(
            preprocessing.transform(heldout)
        )
        self.assertEqual(probabilities.shape, (2, 2))
        self.assertTrue(np.isfinite(probabilities).all())
        self.assertTrue(
            ((probabilities >= 0) & (probabilities <= 1)).all()
        )
        np.testing.assert_allclose(probabilities.sum(axis=1), 1)
        np.testing.assert_array_equal(estimator.classes_, [0, 1])
