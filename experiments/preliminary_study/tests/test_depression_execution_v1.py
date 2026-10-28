import copy
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.depression_execution_v1 import fit_authorized_reference


class ExecutionTests(unittest.TestCase):
    def setUp(self):
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
                "status": "approved_development_evaluation"
            },
            "estimator_specification": {
                "id": "depression_logistic_baseline_v0.1",
                "implementation": "primary_three_field_v1",
            },
        }
        index = pd.Index(["synthetic_a", "synthetic_b", "synthetic_c"])
        self.X = pd.DataFrame({
            "RIDAGEYR": [20, 40, 60],
            "RIAGENDR": [1, 2, 1],
            "INDFMPIR": [1.0, np.nan, 3.0],
        }, index=index)
        self.y = pd.Series([0, 1, 0], index=index)
        self.w = pd.Series([1.0, 2.0, 3.0], index=index)

    def assert_blocked_without_fit(self, config=None, X=None, y=None, w=None):
        with patch("src.depression_execution_v1.fit_reference") as fit:
            with self.assertRaises((PermissionError, ValueError)):
                fit_authorized_reference(
                    self.config if config is None else config,
                    self.X if X is None else X,
                    self.y if y is None else y,
                    self.w if w is None else w,
                )
            fit.assert_not_called()

    def test_missing_false_or_nonboolean_permission_blocks(self):
        for field in ("model_training", "local_baseline_fit"):
            for value in (None, False, "true", 1):
                with self.subTest(field=field, value=value):
                    config = copy.deepcopy(self.config)
                    config["execution_permissions"][field] = value
                    self.assert_blocked_without_fit(config=config)

    def test_pending_approvals_block(self):
        for section in ("predictor_policy", "evaluation"):
            with self.subTest(section=section):
                config = copy.deepcopy(self.config)
                config[section]["status"] = "proposed_not_approved"
                self.assert_blocked_without_fit(config=config)

    def test_unexpected_specification_blocks(self):
        config = copy.deepcopy(self.config)
        config["estimator_specification"]["implementation"] = "secondary"
        self.assert_blocked_without_fit(config=config)

    def test_changed_predictors_block(self):
        config = copy.deepcopy(self.config)
        config["predictor_policy"]["candidate_allowlist"].append("DPQ010")
        self.assert_blocked_without_fit(config=config)

        self.assert_blocked_without_fit(X=self.X.assign(DPQ010=0))

    def test_shuffled_labels_or_weights_block(self):
        self.assert_blocked_without_fit(y=self.y.iloc[::-1])
        self.assert_blocked_without_fit(w=self.w.iloc[::-1])

    def test_duplicate_or_missing_indexes_block(self):
        for values in (
            ["a", "a", "c"],
            ["a", None, "c"],
        ):
            with self.subTest(index=values):
                X = self.X.copy()
                X.index = values
                self.assert_blocked_without_fit(X=X)

    def test_invalid_weights_block_before_fit(self):
        weights = self.w.copy()
        weights.iloc[0] = 0
        self.assert_blocked_without_fit(w=weights)

    def test_valid_synthetic_contract_routes_aligned_arrays(self):
        with patch("src.depression_execution_v1.fit_reference") as fit:
            fit.return_value = ("synthetic_preprocessor", "synthetic_model")
            result = fit_authorized_reference(
                self.config, self.X, self.y, self.w
            )
            self.assertEqual(result, fit.return_value)
            fit.assert_called_once()
            X, y, weights = fit.call_args.args
            pd.testing.assert_frame_equal(X, self.X)
            np.testing.assert_array_equal(y, self.y.to_numpy())
            np.testing.assert_array_equal(weights, self.w.to_numpy())
