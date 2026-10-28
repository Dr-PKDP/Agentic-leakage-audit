"""Score whether a review names the variable that makes a feature selection contradicted.

Scope: contexts whose proposal is a feature selection (families F01, F02 and F07) and whose initial
proposal is contradicted. A variable is offending when the single-variable selection containing it is
contradicted under the context's rule. A review names the variable when its identifier occurs as a whole
word; it flags the variable when, within 160 characters of an occurrence, an exclusion cue appears;
A revision acts on the variable when the variable is absent from the final selection.

Usage: python analysis/review_flags.py --plan-dir PLAN --run-dir RESCORED_RUN_DIR [--out FILE]
RESCORED_RUN_DIR is a directory written by analysis/normalized_rescore.py (per-unit records plus requests.jsonl).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "experiments/extended_v0_5"
sys.path[:0] = [str(EXT), str(ROOT / "experiments/principal_v0_4")]
import p6_extended_v0_5 as x  # noqa: E402

CUE = re.compile(r"exclud|remov|drop|leak|should not|must not|cannot|can't|violat|not be (used|included|selected)|inadmissible|not ready|too late|after the cutoff", re.I)
FAMILIES = ("F01", "F02", "F07")


def offenders(c, p):
    sel = p.get("selected") if isinstance(p, dict) else None
    if not isinstance(sel, list):
        return []
    return [v for v in sel if str(x.evaluate_ext(c, {"selected": [v]})["verdict"]).startswith("contradicted")]


def names(text, var):
    return [m.start() for m in re.finditer(r"(?<![A-Za-z0-9_])" + re.escape(var) + r"(?![A-Za-z0-9_])", text)]


def flagged(text, var):
    for i in names(text, var):
        if CUE.search(text[max(0, i - 160): i + len(var) + 160]):
            return True
    return False


def final_selection(rec, stream):
    if stream == "patch_critic":
        out = (rec.get("paired_patch_paths") or {}).get("outputs", {}).get("interface_only", {})
        art = (out.get("action") or {}).get("artifact")
        return art.get("selected") if isinstance(art, dict) else None
    art = rec.get("final_artifact")
    return art.get("selected") if isinstance(art, dict) else None


def score(plan_dir, run_dir):
    plan_dir, run_dir = Path(plan_dir), Path(run_dir)
    jobs = {j["unit"]: j for j in json.loads((plan_dir / "jobs.json").read_text())}
    ev = [json.loads(s) for s in (run_dir / "requests.jsonl").read_text().splitlines() if s.strip()]
    review = {e["unit"]: e["response"]["choices"][0]["message"]["content"] for e in ev if e["stage"] == "review" and e["status"] == "completed"}
    rows = []
    for unit, j in jobs.items():
        c, p = j["context"], j["initial_proposal"]
        if c["family"] not in FAMILIES or not str(x.evaluate_ext(c, p)["verdict"]).startswith("contradicted"):
            continue
        off = offenders(c, p)
        if not off or unit not in review:
            continue
        rec = json.loads((run_dir / (unit + ".json")).read_text())
        fin = final_selection(rec, j["stream"])
        text = review[unit]
        rows.append({"unit": unit, "stream": j["stream"], "family": c["family"], "n_off": len(off),
                     "named": any(names(text, v) for v in off), "flagged": any(flagged(text, v) for v in off),
                     "acted": isinstance(fin, list) and all(v not in fin for v in off),
                     "any_removed": isinstance(fin, list) and any(v not in fin for v in off)})
    return rows


def summarize(rows):
    out = {}
    for key, sel in (("all", lambda r: True), ("named", lambda r: r["named"]), ("not_named", lambda r: not r["named"]),
                     ("flagged", lambda r: r["flagged"]), ("not_flagged", lambda r: not r["flagged"])):
        s = [r for r in rows if sel(r)]
        out[key] = {"n": len(s), "acted": sum(r["acted"] for r in s)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan-dir", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    rows = score(a.plan_dir, a.run_dir)
    res = {"summary": summarize(rows), "by_stream": {s: summarize([r for r in rows if r["stream"] == s]) for s in sorted({r["stream"] for r in rows})}}
    print(json.dumps(res, indent=1))
    if a.out:
        a.out.write_text(json.dumps({**res, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
