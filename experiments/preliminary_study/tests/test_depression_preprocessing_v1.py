import unittest

import numpy as np
import pandas as pd
from sklearn.exceptions import NotFittedError

from src.depression_preprocessing_v1 import DepressionPreprocessor


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        self.train = pd.DataFrame({
            "RIDAGEYR": [20, 40, 60, 80],
            "RIAGENDR": [1, 2, 1, 2],
            "INDFMPIR": [1.0, np.nan, 3.0, 5.0],
        })

    def test_known_training_statistics(self):
        pre = DepressionPreprocessor().fit(self.train)
        self.assertEqual(pre.income_median_, 3.0)
        np.testing.assert_allclose(pre.scaler_.mean_, [50.0, 3.0])
        np.testing.assert_allclose(pre.scaler_.var_, [500.0, 2.0])

    def test_missingness_and_gender_encoding(self):
        result = DepressionPreprocessor().fit_transform(self.train)
        np.testing.assert_array_equal(result[:, 2], [0, 1, 0, 1])
        np.testing.assert_array_equal(result[:, 3], [0, 1, 0, 0])
        self.assertAlmostEqual(result[1, 1], 0.0)

    def test_heldout_uses_training_statistics_without_mutation(self):
        pre = DepressionPreprocessor().fit(self.train)
        mean_before = pre.scaler_.mean_.copy()
        scale_before = pre.scaler_.scale_.copy()
        heldout = pd.DataFrame({
            "RIDAGEYR": [80],
            "RIAGENDR": [2],
            "INDFMPIR": [np.nan],
        })
        result = pre.transform(heldout)
        self.assertAlmostEqual(result[0, 0], 30 / np.sqrt(500))
        self.assertAlmostEqual(result[0, 1], 0.0)
        np.testing.assert_array_equal(result[0, 2:], [1, 1])

        changed = heldout.copy()
        changed["RIDAGEYR"] = 18
        changed["INDFMPIR"] = 0.0
        pre.transform(changed)

        self.assertEqual(pre.income_median_, 3.0)
        np.testing.assert_array_equal(pre.scaler_.mean_, mean_before)
        np.testing.assert_array_equal(pre.scaler_.scale_, scale_before)

    def test_all_missing_training_income_stops(self):
        bad = self.train.copy()
        bad["INDFMPIR"] = np.nan
        with self.assertRaises(ValueError):
            DepressionPreprocessor().fit(bad)

    def test_invalid_values_stop(self):
        for field, value in [
            ("RIDAGEYR", np.nan),
            ("RIDAGEYR", 17),
            ("RIDAGEYR", 40.5),
            ("RIAGENDR", np.nan),
            ("RIAGENDR", 3),
            ("INDFMPIR", -1),
            ("INDFMPIR", 6),
            ("INDFMPIR", np.inf),
        ]:
            with self.subTest(field=field, value=value):
                bad = self.train.astype(float).copy()
                bad.loc[0, field] = value
                with self.assertRaises(ValueError):
                    DepressionPreprocessor().fit(bad)

    def test_unapproved_extra_column_stops(self):
        bad = self.train.assign(DPQ010=0)
        with self.assertRaises(ValueError):
            DepressionPreprocessor().fit(bad)

    def test_transform_requires_fit(self):
        with self.assertRaises(NotFittedError):
            DepressionPreprocessor().transform(self.train)

    def test_output_is_finite_and_input_unchanged(self):
        original = self.train.copy(deep=True)
        pre = DepressionPreprocessor()
        result = pre.fit_transform(self.train)
        self.assertEqual(result.shape, (4, 4))
        self.assertTrue(np.isfinite(result).all())
        pd.testing.assert_frame_equal(self.train, original)
        self.assertEqual(len(pre.get_feature_names_out()), 4)
