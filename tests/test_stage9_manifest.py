import json


def test_build_manifest_has_required_fields(tmp_path):
    from src.stage9_manifest import build_manifest

    manifest = build_manifest(
        run_id="guarded_multi_agent_seed_20261023",
        agent_name="guarded_multi_agent",
        seed=20261023,
        feature_audit_path="outputs/features/P6_hypertension_feature_guard_audit.csv",
        critic_report_path="outputs/models/P6_STAGE8_hypertension_critic_report.json",
        test_labels_accessed=False,
    )

    assert manifest["run_id"] == "guarded_multi_agent_seed_20261023"
    assert manifest["agent_name"] == "guarded_multi_agent"
    assert manifest["seed"] == 20261023
    assert manifest["test_labels_accessed"] is False
    assert manifest["status"] == "planned"


def test_validate_manifest_rejects_test_label_access():
    from src.stage9_manifest import build_manifest, validate_manifest

    manifest = build_manifest(
        run_id="bad_run",
        agent_name="single_agent",
        seed=1,
        feature_audit_path="audit.csv",
        critic_report_path="critic.json",
        test_labels_accessed=True,
    )

    result = validate_manifest(manifest)

    assert result["status"] == "fail"
    assert "test labels" in result["details"].lower()


def test_save_manifest_writes_valid_json(tmp_path):
    from src.stage9_manifest import build_manifest, save_manifest

    manifest = build_manifest(
        run_id="human_reference_seed_20261023",
        agent_name="human_reference",
        seed=20261023,
        feature_audit_path="audit.csv",
        critic_report_path="critic.json",
        test_labels_accessed=False,
    )

    path = tmp_path / "manifest.json"
    save_manifest(manifest, path)

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run_id"] == manifest["run_id"]