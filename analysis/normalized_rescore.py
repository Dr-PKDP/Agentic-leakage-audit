"""Rescore the revision responses of one run under a fixed normalization rule.

Strict scoring parses the whole response as JSON, as the runner does. Normalized scoring applies,
before scoring, the rules below and nothing else:
  1. remove a Markdown code fence around the response;
  2. parse the first JSON value and ignore any text after it;
  3. for full proposals, unwrap a single-key object whose key is "proposal_schema" or "proposal";
  4. for full proposals, keep only the keys named in the context's proposal schema when all of them are present;
  5. for patches, add context_id, context_sha256 and proposal_sha256 when they are absent.
The remaining content of each response is scored unchanged by the original evaluator and gates.

Usage: python analysis/normalized_rescore.py --plan-dir PLAN --run-dir RUN --out-dir NEW_DIR [--mode strict|normalized]
Copies the run directory to NEW_DIR, rewrites the per-unit records, and runs the extended analysis on it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "experiments/extended_v0_5"
sys.path[:0] = [str(EXT), str(ROOT / "experiments/principal_v0_4")]
import p6_extended_v0_5 as x  # noqa: E402

v4 = x.v4
WRAPPERS = ("proposal_schema", "proposal")
FENCE = re.compile(r"^\s*```[A-Za-z]*\s*\n?(.*?)\n?```\s*$", re.S)


def first_json(text):
    m = FENCE.match(text)
    body = (m.group(1) if m else text).strip()
    obj, _ = json.JSONDecoder().raw_decode(body)
    return obj


def normalize(text, stream, c, p):
    obj = first_json(text)
    if stream == "patch_critic":
        if isinstance(obj, dict) and "operations" in obj:
            obj = {"context_id": c["context_id"], "context_sha256": v4.sha(c), "proposal_sha256": v4.sha(p), **obj}
        return obj
    while isinstance(obj, dict) and len(obj) == 1 and next(iter(obj)) in WRAPPERS and isinstance(next(iter(obj.values())), dict):
        obj = next(iter(obj.values()))
    keys = list(c["proposal_schema"])
    if isinstance(obj, dict) and all(k in obj for k in keys):
        obj = {k: obj[k] for k in keys}
    return obj


def rescore(plan_dir, run_dir, out_dir, mode="normalized"):
    plan_dir, run_dir, out_dir = Path(plan_dir), Path(run_dir), Path(out_dir)
    jobs = {j["unit"]: j for j in json.loads((plan_dir / "jobs.json").read_text())}
    events = [json.loads(s) for s in (run_dir / "requests.jsonl").read_text().splitlines() if s.strip()]
    raw = {e["unit"]: e["response"]["choices"][0]["message"]["content"] for e in events if e["stage"] == "revision" and e["status"] == "completed"}
    shutil.copytree(run_dir, out_dir)
    for f in out_dir.glob("*__*.json"):
        f.unlink()
    for unit, j in jobs.items():
        c, p = j["context"], j["initial_proposal"]
        rec = {"unit": unit, "stream": j["stream"], "seed": j["seed"], "status": "started", "initial_assessment": x.evaluate_ext(c, p)}
        try:
            obj = normalize(raw[unit], j["stream"], c, p) if mode == "normalized" else json.loads(raw[unit])
        except (ValueError, TypeError):
            rec["status"] = "unparseable_output"
        else:
            if j["stream"] == "patch_critic":
                rec["paired_patch_paths"] = v4.assess_paths(c, p, obj)
            else:
                rec["final_artifact"] = obj
                rec["final_assessment"] = x.evaluate_ext(c, obj)
            rec["status"] = "completed"
        v4.write(out_dir / (unit + ".json"), rec)
    subprocess.run([sys.executable, str(EXT / "p6_extended_analyze.py"), "--plan-dir", str(plan_dir), "--run-dir", str(out_dir),
                    "--out-dir", str(out_dir / "analysis")], check=True, env={**os.environ, "PYTHONPATH": str(ROOT / "experiments/principal_v0_4")}, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan-dir", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--mode", choices=["strict", "normalized"], default="normalized")
    a = ap.parse_args()
    rescore(a.plan_dir, a.run_dir, a.out_dir, a.mode)


if __name__ == "__main__":
    main()
