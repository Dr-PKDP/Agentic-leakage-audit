import json


def test_capture_identity_check_rejects_manifest_mismatch(tmp_path, monkeypatch):
    from src import stage9_capture_proposal as module

    run_dir = tmp_path / "stage9_runs"
    run_dir.mkdir()

    manifest = {
        "run_id": "single_agent_seed_20261023",
        "agent_name": "single_agent",
        "seed": 20261023,
    }
    proposal = {
        "run_id": "single_agent_seed_20261023",
        "agent_name": "guarded_multi_agent",
        "seed": 20261023,
    }

    manifest_path = run_dir / "single_agent_seed_20261023_manifest.json"
    proposal_path = tmp_path / "proposal.json"

    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    monkeypatch.setattr(module, "RUN_DIR", run_dir)

    loaded_manifest = module.load_json(manifest_path)
    loaded_proposal = module.load_json(proposal_path)

    mismatches = {
        field: {
            "manifest": loaded_manifest.get(field),
            "proposal": loaded_proposal.get(field),
        }
        for field in ["run_id", "agent_name", "seed"]
        if loaded_manifest.get(field) != loaded_proposal.get(field)
    }

    assert mismatches["agent_name"]["manifest"] == "single_agent"
    assert mismatches["agent_name"]["proposal"] == "guarded_multi_agent"


def test_save_and_load_json_roundtrip(tmp_path):
    from src.stage9_capture_proposal import load_json, save_json

    path = tmp_path / "record.json"
    payload = {"status": "pass", "value": 1}

    save_json(payload, path)

    assert load_json(path) == payload