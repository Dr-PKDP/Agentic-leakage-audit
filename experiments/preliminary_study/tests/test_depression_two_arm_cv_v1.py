import copy
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src.depression_two_arm_cv_v1 import run_two_arm_cv


class TwoArmCVTests(unittest.TestCase):
    def setUp(self):
        n = 40
        index = pd.Index([f"synthetic_{i}" for i in range(n)])
        self.X = pd.DataFrame({
            "RIDAGEYR": 20 + np.arange(n),
            "RIAGENDR": np.tile([1, 2, 2, 1], 10),
            "INDFMPIR": np.tile([1.0, np.nan, 3.0, 5.0], 10),
        }, index=index)
        self.y = pd.Series(np.tile([0, 1, 0, 1], 10), index=index)
        self.w = pd.Series(1.0 + np.arange(n) % 7, index=index)
        self.groups = pd.Series(np.repeat(np.arange(10), 4), index=index)
        self.config = {
            "execution_permissions": {
                "model_training": True,
                "local_baseline_fit": True,
            },
            "predictor_policy": {
                "status": "approved_development_specification",
                "candidate_allowlist": [
                    "RIDAGEYR", "RIAGENDR", "INDFMPIR"
                ],
            },
            "evaluation": {
                "status": "approved_development_evaluation",
                "splitter": "StratifiedGroupKFold",
                "n_splits": 5,
                "shuffle": True,
                "random_state": 42,
                "group_fields": ["SDMVSTRA", "SDMVPSU"],
                "comparison_arms": ["primary", "age_gender"],
            },
            "estimator_specification": {
                "id": "depression_logistic_baseline_v0.1",
                "implementation": "primary_three_field_v1",
            },
        }

    def run_cv(self, **changes):
        values = {
            "config": self.config,
            "X": self.X,
            "y": self.y,
            "weights": self.w,
            "groups": self.groups,
        }
        values.update(changes)
        return run_two_arm_cv(**values)

    def assert_stops_before_fit(self, **changes):
        with patch("src.depression_two_arm_cv_v1.fit_reference") as primary:
            with patch(
                "src.depression_two_arm_cv_v1.fit_secondary_reference"
            ) as secondary:
                with self.assertRaises((ValueError, PermissionError)):
                    self.run_cv(**changes)
                primary.assert_not_called()
                secondary.assert_not_called()

    def test_training_disabled_blocks_both_arms(self):
        config = copy.deepcopy(self.config)
        config["execution_permissions"]["model_training"] = False
        self.assert_stops_before_fit(config=config)

    def test_changed_split_settings_block(self):
        config = copy.deepcopy(self.config)
        config["evaluation"]["random_state"] = 99
        self.assert_stops_before_fit(config=config)

    def test_misaligned_groups_block(self):
        self.assert_stops_before_fit(groups=self.groups.iloc[::-1])

    def test_missing_or_insufficient_groups_block(self):
        missing = self.groups.astype(float).copy()
        missing.iloc[0] = np.nan
        self.assert_stops_before_fit(groups=missing)
        self.assert_stops_before_fit(groups=self.groups % 4)

    def test_participant_overlap_blocks_before_fit(self):
        invalid = [(np.arange(30), np.arange(20, 40))] * 5
        with patch(
            "src.depression_two_arm_cv_v1.StratifiedGroupKFold"
        ) as splitter:
            splitter.return_value.split.return_value = invalid
            self.assert_stops_before_fit()

    def test_repeated_heldout_partition_blocks_before_fit(self):
        valid = list(
            StratifiedGroupKFold(
                n_splits=5, shuffle=True, random_state=42
            ).split(self.X, self.y, self.groups)
        )
        with patch(
            "src.depression_two_arm_cv_v1.StratifiedGroupKFold"
        ) as splitter:
            splitter.return_value.split.return_value = [valid[0]] * 5
            self.assert_stops_before_fit()

    def test_real_synthetic_two_arm_cross_validation(self):
        original = self.X.copy(deep=True)
        probabilities, folds = self.run_cv()
        self.assertEqual(probabilities.shape, (40, 2))
        self.assertEqual(
            list(probabilities.columns), ["primary", "age_gender"]
        )
        self.assertTrue(probabilities.index.equals(self.X.index))
        self.assertTrue(np.isfinite(probabilities.to_numpy()).all())
        self.assertTrue(
            ((probabilities >= 0) & (probabilities <= 1)).to_numpy().all()
        )
        self.assertEqual(len(folds), 5)
        self.assertEqual(sum(f["heldout_rows"] for f in folds), 40)
        pd.testing.assert_frame_equal(self.X, original)
