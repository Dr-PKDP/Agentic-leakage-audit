def test_gate_allows_captured_passing_proposal():
    from src.stage9_execution_gate import check_execution_gate

    manifest = {
        "run_id": "single_agent_seed_20261023",
        "test_labels_accessed": False,
    }
    proposal_record = {
        "run_id": "single_agent_seed_20261023",
        "validation": {"status": "pass"},
    }

    result = check_execution_gate(manifest, proposal_record)

    assert result["status"] == "pass"


def test_gate_blocks_missing_proposal():
    from src.stage9_execution_gate import check_execution_gate

    manifest = {
        "run_id": "single_agent_seed_20261024",
        "test_labels_accessed": False,
    }

    result = check_execution_gate(manifest, None)

    assert result["status"] == "fail"
    assert "missing" in result["details"].lower()


def test_gate_blocks_failed_proposal():
    from src.stage9_execution_gate import check_execution_gate

    manifest = {
        "run_id": "single_agent_seed_20261025",
        "test_labels_accessed": False,
    }
    proposal_record = {
        "run_id": "single_agent_seed_20261025",
        "validation": {"status": "fail"},
    }

    result = check_execution_gate(manifest, proposal_record)

    assert result["status"] == "fail"
    assert "did not pass" in result["details"].lower()


def test_gate_blocks_previously_accessed_test_labels():
    from src.stage9_execution_gate import check_execution_gate

    manifest = {
        "run_id": "single_agent_seed_20261026",
        "test_labels_accessed": True,
    }
    proposal_record = {
        "run_id": "single_agent_seed_20261026",
        "validation": {"status": "pass"},
    }

    result = check_execution_gate(manifest, proposal_record)

    assert result["status"] == "fail"
    assert "already accessed" in result["details"].lower()


def test_gate_blocks_identity_mismatch():
    from src.stage9_execution_gate import check_execution_gate

    manifest = {
        "run_id": "single_agent_seed_20261027",
        "test_labels_accessed": False,
    }
    proposal_record = {
        "run_id": "different_run",
        "validation": {"status": "pass"},
    }

    result = check_execution_gate(manifest, proposal_record)

    assert result["status"] == "fail"
    assert "does not match" in result["details"].lower()