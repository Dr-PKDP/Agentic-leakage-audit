"""Name-prefix rules that exclude outcome-defining NHANES variables from a task's predictor set.

Each task maps to regular expressions over upper-cased variable names. Survey design
variables (strata, PSUs and examination or interview weights) are excluded for every task.
"""
import re

RULES = {
    "T1_diabetes_screening": [r"^(LBXGH|LBDGH|LBXGLU|LBDGLU|LBXIN|LBDIN|DIQ)"],
    "T2_hypertension_screening": [r"^(BPX|BPQ)"],
    "T3_depressive_symptoms": [r"^(DPQ|FNQ)"],
    "T4_ckd_screening": [r"^(LBXSCR|LBDCRE|URXUMA|URXUCR|URDACT|URXUACR|KIQ|CKQ)"],
}
DESIGN = r"^(SDMVSTRA|SDMVPSU|WTMEC|WTINT)"


def flagged(task, features):
    """Return the upper-cased names that the rules for `task` exclude, including design variables."""
    names = [str(x).upper() for x in features]
    return [n for n in names if re.match(DESIGN, n) or any(re.match(p, n) for p in RULES[task])]


def validate(task, features):
    """Return True if any feature matches an outcome-prefix rule for `task`."""
    return any(re.match(p, str(f).upper()) for p in RULES.get(task, []) for f in features)
