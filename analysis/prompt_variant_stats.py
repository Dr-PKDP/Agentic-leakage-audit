"""Clarified revision instruction and review scoring for the second-model and longer-limit runs.

For each arm (core24, nhanes) and each run set (Qwen3-8B at the longer limit with the original and the clarified
instruction, Granite 3.3 8B Instruct with the original and the clarified instruction; Qwen3-8B with the clarified
instruction was run on the core arm only), the script regenerates the plan,
rescores the archived responses strictly and after normalization, tabulates response-format categories and the
gate comparison (as in analysis/second_model_stats.py), and scores the reviews with analysis/review_flags.py.
It writes results/prompt_variant_stats.json and, for the clarified run, strict/ and normalized/ outcome tables.
No model calls.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "experiments/label_contexts"
sys.path[:0] = [str(Path(__file__).parent)]
import normalized_rescore as nr  # noqa: E402
import review_flags as rf  # noqa: E402
import second_model_stats as sm  # noqa: E402

RES = ROOT / "results"
SETS = {
    "qwen3_8b_original": ("review_limit_2048", "original", "p6-qwen3-8b", "http://127.0.0.1:8010/v1"),
    "granite_original": ("granite", "original", "p6-granite-8b", "http://127.0.0.1:8011/v1"),
    "granite_clarified": ("granite_clarified", "clarified", "p6-granite-8b", "http://127.0.0.1:8011/v1"),
    "qwen3_8b_clarified": ("review_limit_2048_clarified", "clarified", "p6-qwen3-8b", "http://127.0.0.1:8010/v1"),
}


def prepare(arm, d, variant, model, url):
    subprocess.run([sys.executable, "p6_extended_v0_5.py", "prepare", "--output-dir", str(d), "--arm", arm, "--context-set", arm, "--thinking", "default",
                    "--seeds", sm.ARMS[arm], "--model", model, "--base-url", url, "--review-max-tokens", "2048", "--revision-max-tokens", "512",
                    "--prompt-variant", variant], cwd=EXT, check=True, capture_output=True,
                   env={**os.environ, "PYTHONPATH": str(ROOT / "experiments/core_contexts")})


def main():
    stats = {}
    for name, (folder, variant, model, url) in SETS.items():
        for arm in sm.ARMS:
            run = RES / folder / arm
            if not (run / "requests.jsonl").exists():
                continue
            events = [json.loads(s) for s in (run / "requests.jsonl").read_text().splitlines() if s.strip()]
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                prepare(arm, tmp / "plan", variant, model, url)
                jobs = {j["unit"]: j for j in json.loads((tmp / "plan/jobs.json").read_text())}
                res = {"formats": sm.formats(jobs, events)}
                for mode in ("strict", "normalized"):
                    nr.rescore(tmp / "plan", run, tmp / mode, mode)
                    rows = list(csv.DictReader((tmp / mode / "analysis/outcomes.csv").open()))
                    res[mode] = {"paths": sm.table(rows), "gate_comparison": sm.gates(rows)}
                    if variant == "clarified":
                        dest = run / mode
                        dest.mkdir(exist_ok=True)
                        for f in ("outcomes.csv", "summary.json"):
                            (dest / f).write_bytes((tmp / mode / "analysis" / f).read_bytes())
                rows = rf.score(tmp / "plan", tmp / "strict")
                res["review_flags"] = {"summary": rf.summarize(rows), "by_stream": {s: rf.summarize([r for r in rows if r["stream"] == s]) for s in sorted({r["stream"] for r in rows})}}
            stats.setdefault(name, {})[arm] = res
    (RES / "prompt_variant_stats.json").write_text(json.dumps(stats, indent=1) + "\n")


if __name__ == "__main__":
    main()
