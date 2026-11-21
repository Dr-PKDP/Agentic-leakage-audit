"""Statistics for the second-model run (Granite 3.3 8B Instruct, review limit 2,048 tokens).

Rescores the archived responses in results/granite strictly and after normalization
(analysis/normalized_rescore.py), tabulates outcomes, response-format categories and the gate comparison,
and writes results/granite/stats.json plus the rescored outcomes. No model calls.
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/granite"
EXT = ROOT / "experiments/label_contexts"
sys.path[:0] = [str(Path(__file__).parent)]
import normalized_rescore as nr  # noqa: E402

PATHS = ["self_review", "structure_feedback", "evidence_critic", "patch_critic/interface_only", "patch_critic/evidence_guarded"]
ARMS = {"core24": "42", "nhanes": "42,43"}
FENCE = re.compile(r"^\s*```[A-Za-z]*\s*\n?(.*?)\n?```\s*$", re.S)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return round(min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n), 4)


def prepare(arm, d):
    subprocess.run([sys.executable, "p6_extended_v0_5.py", "prepare", "--output-dir", str(d), "--arm", arm, "--context-set", arm, "--thinking", "default",
                    "--seeds", ARMS[arm], "--model", "p6-granite-8b", "--base-url", "http://127.0.0.1:8011/v1", "--review-max-tokens", "2048",
                    "--revision-max-tokens", "512"], cwd=EXT, check=True, capture_output=True,
                   env={**os.environ, "PYTHONPATH": str(ROOT / "experiments/core_contexts")})


def formats(jobs, events):
    c, n = Counter(), Counter()
    for e in events:
        if e["stage"] != "revision":
            continue
        j = jobs[e["unit"]]
        kind = "patch" if j["stream"] == "patch_critic" else "full"
        n[kind] += 1
        text = e["response"]["choices"][0]["message"]["content"]
        m = FENCE.match(text)
        body = (m.group(1) if m else text).strip()
        c[kind, "fenced"] += bool(m)
        try:
            obj, end = json.JSONDecoder().raw_decode(body)
        except ValueError:
            c[kind, "no_json"] += 1
            continue
        c[kind, "text_after_json"] += bool(body[end:].strip())
        if kind == "full":
            inner = obj
            c[kind, "nested_under_wrapper_key"] += isinstance(obj, dict) and len(obj) == 1 and next(iter(obj)) in nr.WRAPPERS
            while isinstance(inner, dict) and len(inner) == 1 and next(iter(inner)) in nr.WRAPPERS:
                inner = next(iter(inner.values()))
            keys = list(j["context"]["proposal_schema"])
            has = isinstance(inner, dict) and all(k in inner for k in keys)
            c[kind, "schema_keys_missing"] += not has
            c[kind, "extra_keys"] += has and bool(set(inner) - set(keys))
            c[kind, "same_as_input"] += inner == j["initial_proposal"]
        elif isinstance(obj, dict):
            c[kind, "envelope_fields_missing"] += any(k not in obj for k in ("context_id", "context_sha256", "proposal_sha256"))
            ops = obj.get("operations")
            c[kind, "operation_names_unknown_field"] += isinstance(ops, list) and any(op.get("field") not in j["initial_proposal"] for op in ops if isinstance(op, dict))
    return {"responses": dict(n), "categories": {f"{k}|{v}": c[(k, v)] for k, v in sorted(c)}}


def table(rows):
    out = {}
    for p in PATHS + ["prefix_rule_reviser"]:
        rr = [r for r in rows if r["path"] == p]
        if not rr:
            continue
        con = [r for r in rr if r["initial"] == "contradicted_contract"]
        sup = [r for r in rr if r["initial"] == "supported"]
        out[p] = {"repair": [sum(r["final"] == "supported" for r in con), len(con)], "preserve": [sum(r["final"] == "supported" for r in sup), len(sup)],
                  "harmful": sum(r["final"] == "contradicted_contract" for r in sup),
                  "scored_without_format_failure": sum(r["pipeline"] == "assessable" and not r["action"].startswith("fallback") for r in rr),
                  "responses": len(rr)}
    return out


def gates(rows):
    A = {r["unit"]: r for r in rows if r["path"] == PATHS[3]}
    G = {r["unit"]: r for r in rows if r["path"] == PATHS[4]}
    pairs = [(A[u], G[u]) for u in A if A[u]["initial"] == "supported" and A[u]["status"] == G[u]["status"] == "completed"]
    b = sum(a["final"] == "contradicted_contract" and g["final"] != "contradicted_contract" for a, g in pairs)
    c = sum(a["final"] != "contradicted_contract" and g["final"] == "contradicted_contract" for a, g in pairs)
    return {"parseable_pairs": len(pairs), "only_gate_B_better": b, "only_gate_A_better": c, "exact_mcnemar_p": mcnemar(b, c)}


def main():
    stats = {}
    for arm in ARMS:
        run = RES / arm
        events = [json.loads(s) for s in (run / "requests.jsonl").read_text().splitlines() if s.strip()]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            prepare(arm, tmp / "plan")
            jobs = {j["unit"]: j for j in json.loads((tmp / "plan/jobs.json").read_text())}
            res = {"formats": formats(jobs, events)}
            for mode in ("strict", "normalized"):
                nr.rescore(tmp / "plan", run, tmp / mode, mode)
                rows = list(csv.DictReader((tmp / mode / "analysis/outcomes.csv").open()))
                res[mode] = {"paths": table(rows), "gate_comparison": gates(rows)}
                dest = run / mode
                dest.mkdir(exist_ok=True)
                for f in ("outcomes.csv", "summary.json"):
                    (dest / f).write_bytes((tmp / mode / "analysis" / f).read_bytes())
            as_run = json.loads((run / "summary_strict_as_run.json").read_text())["by_path"]
            strict = json.loads((run / "strict/summary.json").read_text())["by_path"]
            res["strict_rescoring_matches_run"] = as_run == strict
        stats[arm] = res
    (RES / "stats.json").write_text(json.dumps(stats, indent=1) + "\n")


if __name__ == "__main__":
    main()
