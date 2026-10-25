def test_valid_proposal_passes():
    from src.stage9_proposal_validator import validate_proposal

    proposal = {
        "run_id": "guarded_multi_agent_seed_20261023",
        "agent_name": "guarded_multi_agent",
        "seed": 20261023,
        "predictors": ["RIDAGEYR", "RIAGENDR", "ALQ130", "phq9_total"],
        "target": "undiagnosed_hypertension",
        "training_cycles": ["2011-2012", "2013-2014", "2015-2016"],
        "evaluation_cycle": "2021-2023",
        "request_test_labels": False,
        "model": {"name": "random_forest"},
    }

    result = validate_proposal(proposal)

    assert result["status"] == "pass"


def test_forbidden_predictor_fails():
    from src.stage9_proposal_validator import validate_proposal

    proposal = {
        "run_id": "bad",
        "agent_name": "single_agent",
        "seed": 1,
        "predictors": ["RIDAGEYR", "BPXSY1"],
        "target": "undiagnosed_hypertension",
        "training_cycles": ["2011-2012"],
        "evaluation_cycle": "2021-2023",
        "request_test_labels": False,
        "model": {"name": "random_forest"},
    }

    result = validate_proposal(proposal)

    assert result["status"] == "fail"
    assert "BPXSY1" in result["details"]


def test_survey_weight_as_predictor_fails():
    from src.stage9_proposal_validator import validate_proposal

    proposal = {
        "run_id": "bad_weight",
        "agent_name": "single_agent",
        "seed": 1,
        "predictors": ["RIDAGEYR", "WTMEC2YR"],
        "target": "undiagnosed_hypertension",
        "training_cycles": ["2011-2012"],
        "evaluation_cycle": "2021-2023",
        "request_test_labels": False,
        "model": {"name": "random_forest"},
    }

    result = validate_proposal(proposal)

    assert result["status"] == "fail"
    assert "WTMEC2YR" in result["details"]


def test_test_label_request_fails():
    from src.stage9_proposal_validator import validate_proposal

    proposal = {
        "run_id": "bad_labels",
        "agent_name": "single_agent",
        "seed": 1,
        "predictors": ["RIDAGEYR"],
        "target": "undiagnosed_hypertension",
        "training_cycles": ["2011-2012"],
        "evaluation_cycle": "2021-2023",
        "request_test_labels": True,
        "model": {"name": "random_forest"},
    }

    result = validate_proposal(proposal)

    assert result["status"] == "fail"
    assert "labels" in result["details"].lower()


def test_overlap_between_training_and_evaluation_fails():
    from src.stage9_proposal_validator import validate_proposal

    proposal = {
        "run_id": "bad_overlap",
        "agent_name": "single_agent",
        "seed": 1,
        "predictors": ["RIDAGEYR"],
        "target": "undiagnosed_hypertension",
        "training_cycles": ["2011-2012", "2021-2023"],
        "evaluation_cycle": "2021-2023",
        "request_test_labels": False,
        "model": {"name": "random_forest"},
    }

    result = validate_proposal(proposal)

    assert result["status"] == "fail"
    assert "overlaps" in result["details"].lower()
