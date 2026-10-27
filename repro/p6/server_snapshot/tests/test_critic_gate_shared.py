import json
import unittest
from pathlib import Path


import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pilot_critic_gate import evaluate_gate


class GateTests(unittest.TestCase):
    def test_consistent_approval_allowed(self):
        result = evaluate_gate({
            "decision": "approve",
            "issues": [],
            "required_changes": []
        })
        self.assertTrue(result["execution_allowed"])
        self.assertEqual(result["gate_decision"], "allow")

    def test_revision_blocked(self):
        result = evaluate_gate({
            "decision": "revise",
            "issues": ["Missing validation rule."],
            "required_changes": ["Specify validation rule."]
        })
        self.assertFalse(result["execution_allowed"])

    def test_rejection_blocked(self):
        result = evaluate_gate({
            "decision": "reject",
            "issues": [],
            "required_changes": []
        })
        self.assertFalse(result["execution_allowed"])

    def test_approve_with_issues_blocked(self):
        result = evaluate_gate({
            "decision": "approve",
            "issues": ["Unresolved issue."],
            "required_changes": []
        })
        self.assertFalse(result["execution_allowed"])

    def test_approve_with_changes_blocked(self):
        result = evaluate_gate({
            "decision": "approve",
            "issues": [],
            "required_changes": ["Change the plan."]
        })
        self.assertFalse(result["execution_allowed"])

    def test_nonapproval_without_details_blocked(self):
        result = evaluate_gate({
            "decision": "revise",
            "issues": [],
            "required_changes": []
        })
        self.assertFalse(result["execution_allowed"])

    def test_malformed_reviews_blocked(self):
        malformed = [
            None,
            [],
            {},
            {"decision": "approve", "issues": []},
            {
                "decision": "approve",
                "issues": [],
                "required_changes": [],
                "extra": True
            },
            {
                "decision": "unknown",
                "issues": [],
                "required_changes": []
            },
            {
                "decision": [],
                "issues": [],
                "required_changes": []
            },
            {
                "decision": "approve",
                "issues": "",
                "required_changes": []
            },
            {
                "decision": "approve",
                "issues": [123],
                "required_changes": []
            },
            {
                "decision": "approve",
                "issues": [],
                "required_changes": ["   "]
            }
        ]

        for review in malformed:
            with self.subTest(review=review):
                result = evaluate_gate(review)
                self.assertFalse(result["execution_allowed"])
                self.assertEqual(result["gate_decision"], "block")
                self.assertIn(
                    "Invalid critic review structure.",
                    result["reasons"]
                )

    def test_known_blind_spot(self):
        # A consistent but scientifically wrong approval is not detectable here.
        result = evaluate_gate({
            "decision": "approve",
            "issues": [],
            "required_changes": []
        })
        self.assertTrue(result["execution_allowed"])
        self.assertEqual(
            result["scope"],
            "consistency_gate_only_not_scientific_validation"
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GateTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    summary = {
        "gate_version": "pilot_v2",
        "test_methods_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "note": (
            "Malformed-input cases run as subtests. "
            "Passing tests do not establish scientific validity."
        )
    }

    path = Path(__file__).with_name("gate_test_results_shared.json")
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print("\n" + json.dumps(summary, indent=2))

    raise SystemExit(0 if result.wasSuccessful() else 1)
