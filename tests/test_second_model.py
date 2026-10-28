import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "analysis"), str(ROOT / "experiments/extended_v0_5"), str(ROOT / "experiments/principal_v0_4")]
import normalized_rescore as nr  # noqa: E402

CTX = {"proposal_schema": {"selected": {"type": "string_list"}}, "context_id": "c"}
PROPOSAL = {"selected": ["A", "B"]}


def test_normalization_rules():
    plain = '{"selected": ["A"]}'
    assert nr.normalize(plain, "self_review", CTX, PROPOSAL) == {"selected": ["A"]}
    fenced = '```json\n{"proposal_schema": {"selected": ["A"]}}\n```'
    assert nr.normalize(fenced, "self_review", CTX, PROPOSAL) == {"selected": ["A"]}
    trailing = '{"proposal": {"selected": ["A"], "note": "x"}}\n\nExplanation: text'
    assert nr.normalize(trailing, "evidence_critic", CTX, PROPOSAL) == {"selected": ["A"]}
    patch = nr.normalize('{"operations": []}', "patch_critic", CTX, PROPOSAL)
    assert set(patch) == {"context_id", "context_sha256", "proposal_sha256", "operations"}
    assert nr.normalize('{"context_id": "c", "operations": []}', "patch_critic", CTX, PROPOSAL)["context_id"] == "c"


def test_second_model_statistics_reproduce_reported_values():
    subprocess.run([sys.executable, str(ROOT / "analysis/second_model_stats.py")], check=True, capture_output=True)
    s = json.loads((ROOT / "results/second_model_granite/stats.json").read_text())
    assert s["core24"]["strict_rescoring_matches_run"] and s["nhanes"]["strict_rescoring_matches_run"]
    core, label = s["core24"]["normalized"]["paths"], s["nhanes"]["normalized"]["paths"]
    assert [core[p]["repair"][0] for p in list(core)] == [8, 8, 12, 11, 10]
    assert [label[p]["repair"][0] for p in list(label)[:5]] == [1, 0, 0, 1, 1]
    assert s["core24"]["strict"]["paths"]["self_review"]["scored_without_format_failure"] == 6
    assert s["core24"]["normalized"]["gate_comparison"] == {"parseable_pairs": 23, "only_gate_B_better": 5, "only_gate_A_better": 0, "exact_mcnemar_p": 0.0625}
    assert s["nhanes"]["formats"]["categories"]["full|same_as_input"] == 176
