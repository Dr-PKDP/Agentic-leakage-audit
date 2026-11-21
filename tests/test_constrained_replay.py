import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/constrained_and_replay"
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "experiments/core_contexts")}


def run(*args, cwd=EXP):
    return subprocess.run([sys.executable, *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True).stdout


def test_offline_check_builds_every_schema_and_verifies_runner_hashes():
    out = json.loads(run("p6_v06.py", "check"))
    assert out["status"] == "PASS_OFFLINE" and out["model_calls"] == 0
    assert out["schemas_built"] == 164 and out["v4_hash_ok"] and out["ext_hash_ok"]


def test_response_schemas_use_only_keywords_the_server_grammar_accepts():
    sys.path.insert(0, str(EXP))
    import p6_v06 as v
    x = v.x
    for setname in ("core24", "nhanes"):
        for it in x.context_items(setname):
            c, p = it["public"], it["valid_or_conservative"]
            for stream in ("self_review", "patch_critic"):
                text = json.dumps(v.response_schema(c, p, stream))
                assert "uniqueItems" not in text
    sch = v.response_schema(c, p, "self_review")
    assert sch["additionalProperties"] is False and list(sch["properties"]) == list(c["proposal_schema"])


def test_gate_battery_reproduces_the_archived_summary(tmp_path):
    out = tmp_path / "gb"
    run("p6_v06_gate_battery.py", "--out-dir", str(out))
    new = json.loads((out / "summary.json").read_text())
    old = json.loads((ROOT / "results/gate_operating_characteristics/summary.json").read_text())
    assert new == old
    assert (out / "edits.csv").read_bytes() == (ROOT / "results/gate_operating_characteristics/edits.csv").read_bytes()
    assert new["edits"] == 474 and new["candidate_artifacts"] == 556
    harmful = new["by_ids_and_class"]["applicable_ids|harmful"]
    assert (harmful["n"], harmful["interface_accepts"], harmful["evidence_gate_accepts"]) == (93, 83, 27)
    for mode in ("no_ids", "foreign_scope_ids", "nonexistent_ids"):
        assert all(v["evidence_gate_accepts"] == 0 for k, v in new["by_ids_and_class"].items() if k.startswith(mode))


def test_statistics_reproduce_reported_values():
    subprocess.run([sys.executable, str(ROOT / "analysis/replay_decoding_execution_stats.py")], check=True, capture_output=True)
    s = json.loads((ROOT / "results/replay_decoding_execution_stats.json").read_text())
    lab, core = s["replay"]["nhanes"], s["replay"]["core24"]
    assert lab["reviews"] == {"source_units": 272, "with_saved_review": 272, "truncated": 239}
    assert core["reviews"]["truncated"] == 90
    c = lab["pooled_complete_vs_cut"]
    assert (c["pairs"], c["first"], c["second"], c["only_first"], c["only_second"]) == (136, 122, 87, 37, 2)
    c = core["pooled_complete_vs_cut"]
    assert (c["pairs"], c["first"], c["second"]) == (84, 71, 68)
    assert lab["pooled_complete_vs_source_run"]["first"] == lab["pooled_complete_vs_source_run"]["second"] == 122
    for model in s["constrained"].values():
        for arm in model.values():
            assert arm["failed_units"] == 0
    e = s["execution"]
    assert e["assessable"] == 3030 and e["agreement"]["rows"] == [2989, 3030]
    assert e["patch_pairs_supported_start"] == {"pairs": 231, "interface_only_inflated": 32, "evidence_gate_inflated": 3}


def test_model_scale_runs_are_complete_and_summaries_match_the_archive():
    base = ROOT / "results/model_scale/qwen3_27b"
    expected = {"q27b_clar_core24": 384, "q27b_con_core24": 384, "q27b_clar_nhanes": 544, "q27b_con_nhanes": 544}
    for arm, requests in expected.items():
        rep = json.loads((base / arm / "run_report.json").read_text())
        assert rep["generation_requests"] == requests and rep["failed_or_unparseable_units"] == 0
    stats = json.loads((ROOT / "results/replay_decoding_execution_stats.json").read_text())["model_scale"]
    assert stats["core24"]["qwen3_27b_constrained"]["evidence_critic"]["repair"] == [21, 21]
    assert stats["nhanes"]["qwen3_27b_constrained"]["patch_critic/evidence_guarded"]["repair"] == [21, 34]


def test_reference_agreement_reports_perfect_agreement_for_a_copy_of_the_reference(tmp_path):
    import csv
    ref = list(csv.DictReader(open(ROOT / "results/nhanes/schema_audit_reference.csv", encoding="utf-8")))
    tasks = {"T1": "T1_diabetes_screening", "T2": "T2_hypertension_screening", "T3": "T3_depressive_symptoms", "T4": "T4_ckd_screening"}
    for t, name in tasks.items():
        names = sorted({r["variable"] for r in ref if r["task"] == name} | {"ZZ_OTHER1", "ZZ_OTHER2", "ZZ_OTHER3"})
        with open(tmp_path / f"ratings_a_{t}.csv", "w", newline="", encoding="utf-8") as h:
            w = csv.writer(h); w.writerow(["variable", "exclude", "criterion", "reason"])
            for v in names:
                w.writerow([v, 0 if v.startswith("ZZ_") else 1, "none" if v.startswith("ZZ_") else "A", ""])
    out = run("reference_agreement.py", "--ratings", str(tmp_path), "--raters", "a", "--out", str(tmp_path / "o"), cwd=ROOT / "analysis")
    summary = json.loads((tmp_path / "o/reference_agreement.json").read_text())
    assert summary["raters"]["a"]["pooled_kappa"] == 1.0
