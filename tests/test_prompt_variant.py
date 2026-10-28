import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "analysis"), str(ROOT / "experiments/extended_v0_5"), str(ROOT / "experiments/principal_v0_4")]
import review_flags as rf  # noqa: E402


def test_review_text_rules():
    text = "Remove LBXGH because it defines the outcome. LBXSCH is a lipid measure."
    assert rf.names(text, "LBXGH") and not rf.names(text, "LBX")
    assert rf.flagged(text, "LBXGH")
    assert not rf.flagged("LBXSCH is a lipid measure and is acceptable.", "LBXSCH")
    assert not rf.names("LBXGH2 appears", "LBXGH")


def test_prompt_variant_statistics_reproduce_reported_values():
    subprocess.run([sys.executable, str(ROOT / "analysis/prompt_variant_stats.py")], check=True, capture_output=True)
    s = json.loads((ROOT / "results/prompt_variant_stats.json").read_text())
    core = s["granite_clarified"]["core24"]["strict"]["paths"]
    assert [core[p]["repair"][0] for p in core] == [9, 8, 13, 10, 9]
    assert [core[p]["scored_without_format_failure"] for p in list(core)[:3]] == [46, 44, 48]
    label = s["granite_clarified"]["nhanes"]["strict"]["paths"]
    assert [label[p]["repair"][0] for p in list(label)[:5]] == [0, 1, 1, 1, 1]
    assert s["granite_clarified"]["nhanes"]["review_flags"]["summary"]["flagged"] == {"n": 53, "acted": 3}
    assert s["qwen3_8b_original"]["nhanes"]["review_flags"]["summary"]["flagged"] == {"n": 132, "acted": 122}
