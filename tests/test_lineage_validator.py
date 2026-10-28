import pytest

from nhanes.lineage_validator import RULES, flagged, validate

CASES = [
    ("T1_diabetes_screening", "LBXGH"),
    ("T2_hypertension_screening", "BPXSY1"),
    ("T3_depressive_symptoms", "DPQ010"),
    ("T4_ckd_screening", "LBXSCR"),
]


@pytest.mark.parametrize("task,name", CASES)
def test_defining_variable_is_flagged(task, name):
    assert validate(task, [name])
    assert flagged(task, [name]) == [name]


@pytest.mark.parametrize("task", sorted(RULES))
def test_unrelated_variable_is_not_flagged(task):
    assert not validate(task, ["RIDAGEYR"])
    assert flagged(task, ["RIDAGEYR"]) == []


@pytest.mark.parametrize("task", sorted(RULES))
def test_design_variables_are_flagged_but_do_not_trigger_validate(task):
    names = ["SDMVSTRA", "SDMVPSU", "WTMEC2YR", "WTINT2YR"]
    assert flagged(task, names) == names
    assert not validate(task, names)


def test_matching_is_case_insensitive():
    assert flagged("T3_depressive_symptoms", ["dpq020"]) == ["DPQ020"]


def test_rules_are_task_specific():
    assert not validate("T3_depressive_symptoms", ["BPXSY1"])
