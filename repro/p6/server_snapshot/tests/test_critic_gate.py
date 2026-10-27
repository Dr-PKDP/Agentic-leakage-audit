import json
import unittest
from pathlib import Path


def evaluate_gate(review):
    fields = {"decision", "issues", "required_changes"}

    valid = (
        isinstance(review, dict)
        and set(review) == fields
        and isinstance(review["decision"], str)
        and review["decision"] in {"approve", "revise", "reject"}
        and isinstance(review["issues"], list)
        and isinstance(review["required_changes"], list)
        and all(
            isinstance(item, str) and bool(item.strip())
            for item in review["issues"]
        )
        and all(
            isinstance(item, str) and bool(item.strip())
            for item in review["required_changes"]
        )
    )

    reasons = []
    if not valid:
        reasons.append("Invalid critic review structure.")
    else:
        if review["decision"] != "approve":
            reasons.append("Critic did not approve.")
        if review["issues"]:
            reasons.append("Critic reported unresolved issues.")
        if review["required_changes"]:
            reasons.append("Critic requested changes.")

    allowed = valid and not reasons
    return {
        "gate_version": "pilot_v2",
        "execution_allowed": allowed,
        "gate_decision": "allow" if allowed else "block",
        "reasons": reasons,
        "scope": "consistency_gate_only_not_scientific_validation"
    }


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

    path = Path(__file__).with_name("gate_test_results.json")
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print("\n" + json.dumps(summary, indent=2))

    raise SystemExit(0 if result.wasSuccessful() else 1)
