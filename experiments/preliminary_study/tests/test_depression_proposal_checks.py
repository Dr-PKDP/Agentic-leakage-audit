import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.depression_proposal_checks import check_proposal, PENDING

class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.base = {"predictors": ["RIDAGEYR"], "excluded": ["All DPQ fields"], "survey_plan": "Placeholder, not an adequate scientific plan.", "validation_plan": "Join checks only, not predictive validation.", "unresolved_decisions": sorted(PENDING)}

    def test_valid_structure_not_scientific_approval(self):
        r = check_proposal(self.base)
        self.assertTrue(r["structure_valid"])
        self.assertEqual(r["scientific_validity"], "not_assessed")
        self.assertFalse(r["execution_authorized"])

    def test_bad_structures(self):
        cases = [None, [], {}]
        for field in self.base:
            p = copy.deepcopy(self.base)
            del p[field]
            cases.append(p)
        p = copy.deepcopy(self.base)
        p["extra"] = True
        cases.append(p)
        for p in cases:
            with self.subTest(proposal=p):
                r = check_proposal(p)
                self.assertFalse(r["structure_valid"])
                self.assertFalse(r["execution_authorized"])

    def test_bad_field_values(self):
        for field in self.base:
            bad = [None, 123, {}, "", "   "]
            if isinstance(self.base[field], list):
                bad += [[123], ["   "], ["duplicate", "duplicate"]]
            else:
                bad += [[]]
            for value in bad:
                with self.subTest(field=field, value=value):
                    p = copy.deepcopy(self.base)
                    p[field] = value
                    self.assertFalse(check_proposal(p)["structure_valid"])

    def test_pending_coverage(self):
        ids = sorted(PENDING)
        for values in ([], ids[:-1], ids + ["unknown"], ids + [ids[0]]):
            with self.subTest(values=values):
                p = copy.deepcopy(self.base)
                p["unresolved_decisions"] = values
                self.assertFalse(check_proposal(p)["structure_valid"])

    def test_pending_order_irrelevant(self):
        p = copy.deepcopy(self.base)
        p["unresolved_decisions"].reverse()
        self.assertTrue(check_proposal(p)["structure_valid"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
