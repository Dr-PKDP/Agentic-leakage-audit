import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_replay_reproduces_reported_scores(tmp_path):
    out = tmp_path / "gen"
    subprocess.run([sys.executable, str(ROOT / "reproduce.py"), "--out", str(out)], check=True, capture_output=True)
    summary = json.loads((out / "summary.json").read_text())
    p = summary["principal"]
    assert (p["exact_units"], p["requests"], p["total_tokens"], p["review_limit_stops"]) == (192, 384, 543571, 93)
    c = summary["pilot"]["conditions"]
    assert [c[k]["strict_final_pass"] for k in ("single_self_review", "structure_feedback", "guarded_critic")] == [1, 7, 4]
    assert [c[k]["normalized_final_pass"] for k in ("single_self_review", "structure_feedback", "guarded_critic")] == [3, 7, 4]
    assert summary["reference"]["cohort"]["complete_outcome"] == 5068


def test_schema_audit_counts(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "analysis/schema_audit.py")], check=True, capture_output=True)
    audit = json.loads((ROOT / "results/nhanes/schema_audit.json").read_text())
    tasks = [k for k in audit if k.startswith("T")]
    assert sum(audit[t]["reference_n"] for t in tasks) == 80
    assert sum(audit[t]["flagged_of_reference"] for t in tasks) == 33
    rows = list(csv.DictReader((ROOT / "results/nhanes/schema_audit_reference.csv").open()))
    assert len(rows) == 80
