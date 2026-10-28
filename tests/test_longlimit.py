import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "experiments/extended_v0_5"
LL = ROOT / "results/longlimit_2048"


def prepare(tmp_path, *extra):
    env = {"PYTHONPATH": str(ROOT / "experiments/principal_v0_4")}
    out = subprocess.run(
        [sys.executable, "p6_extended_v0_5.py", "prepare", "--output-dir", str(tmp_path / "plan"),
         "--arm", "t", "--context-set", "core24", "--thinking", "default", "--seeds", "42",
         "--model", "m", "--base-url", "http://127.0.0.1:9/v1", "--workers", "1", *extra],
        cwd=EXT, env={**__import__("os").environ, **env}, capture_output=True, text=True, check=True,
    ).stdout
    plan = next((tmp_path / "plan").glob("*plan*.json"))
    return json.loads(out), json.loads(plan.read_text())


def test_limits_are_recorded_in_the_plan(tmp_path):
    _, plan = prepare(tmp_path, "--review-max-tokens", "2048", "--revision-max-tokens", "512")
    assert plan["review_max_tokens"] == 2048 and plan["max_tokens"] == 512


def test_default_limits_match_the_principal_run(tmp_path):
    _, plan = prepare(tmp_path)
    assert plan["review_max_tokens"] == 1024 and plan["max_tokens"] == 1024


def test_longlimit_statistics_reproduce_reported_values():
    subprocess.run([sys.executable, str(ROOT / "analysis/longlimit_stats.py")], check=True, capture_output=True)
    s = json.loads((LL / "stats.json").read_text())
    assert s["requests_core24"]["review"]["finish_reasons"] == {"stop": 192}
    assert s["requests_nhanes"]["review"]["finish_reasons"] == {"stop": 263, "length": 9}
    assert s["requests_old_nhanes"]["review"]["finish_reasons"]["length"] == 238
    assert (s["pooled_repair_core24"]["old"], s["pooled_repair_core24"]["new"]) == (82.1, 84.5)
    assert (s["pooled_repair_nhanes"]["old"], s["pooled_repair_nhanes"]["new"]) == (64.0, 89.7)
    assert s["gate_nhanes_long"]["only_B_better"] == 4 and s["gate_nhanes_long"]["only_A_better"] == 0
    assert s["gate_core_long_discordant"] == 0
    new = s["nhanes"]["limit2048"]
    assert [new[p]["repair"][0] for p in
            ("self_review", "structure_feedback", "evidence_critic",
             "patch_critic/interface_only", "patch_critic/evidence_guarded")] == [30, 30, 30, 33, 32]
    assert new["prefix_rule_reviser"]["repair"][:2] == [6, 17]
