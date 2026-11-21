"""Agreement between AI-tool raters and the NHANES reference exclusion sets.

Input: one CSV per rater and task (ratings_<rater>_T1.csv ... T4.csv) with the columns variable, exclude, criterion, reason,
each covering the candidate pool of that task. Reference: results/nhanes/schema_audit_reference.csv.
Output: reference_agreement.json and disagreements.csv (every task-variable pair on which a rater differs from the reference or the
raters differ from each other, with empty columns for a human cross-check).

Usage: python reference_agreement.py --ratings DIR --raters chatgpt perplexity [--reference PATH] [--out DIR]
"""
import argparse
import csv
import json
from pathlib import Path

TASKS = {"T1": "T1_diabetes_screening", "T2": "T2_hypertension_screening", "T3": "T3_depressive_symptoms", "T4": "T4_ckd_screening"}


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def read_ratings(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as h:
        for r in csv.DictReader(h):
            out[r["variable"].strip()] = (int(str(r["exclude"]).strip()), r.get("criterion", "").strip(), r.get("reason", "").strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratings", type=Path, required=True)
    ap.add_argument("--raters", nargs="+", required=True)
    ap.add_argument("--reference", type=Path, default=Path(__file__).resolve().parents[1] / "results/nhanes/schema_audit_reference.csv")
    ap.add_argument("--out", type=Path, default=Path("."))
    a = ap.parse_args()
    ref = {}
    cat = {}
    with open(a.reference, newline="", encoding="utf-8") as h:
        for r in csv.DictReader(h):
            ref[(r["task"], r["variable"])] = 1
            cat[(r["task"], r["variable"])] = r["category"]
    data = {r: {} for r in a.raters}
    for r in a.raters:
        for t in TASKS:
            data[r][t] = read_ratings(a.ratings / f"ratings_{r}_{t}.csv")
    pool = {t: sorted(set.intersection(*(set(data[r][t]) for r in a.raters))) for t in TASKS}
    summary = {"pool_per_task": {t: len(v) for t, v in pool.items()}, "reference_pairs_per_task": {t: sum(1 for k in ref if k[0] == TASKS[t]) for t in TASKS},
               "reference_pairs_outside_pool": sorted(f"{k[0]}:{k[1]}" for k in ref if k[1] not in pool[[t for t, v in TASKS.items() if v == k[0]][0]]),
               "raters": {}, "between_raters": {}}
    for r in a.raters:
        per = {}
        allr, allx = [], []
        for t in TASKS:
            x = [data[r][t][v][0] for v in pool[t]]
            y = [ref.get((TASKS[t], v), 0) for v in pool[t]]
            tp = sum(i and j for i, j in zip(x, y)); fn = sum((not i) and j for i, j in zip(x, y)); fp = sum(i and (not j) for i, j in zip(x, y))
            per[t] = {"kappa": kappa(x, y), "agree": sum(i == j for i, j in zip(x, y)), "n": len(x), "reference_flagged_by_rater": [tp, tp + fn],
                      "rater_flags_outside_reference": fp}
            allr += y; allx += x
        summary["raters"][r] = {"pooled_kappa": kappa(allx, allr), "per_task": per}
    for i, r in enumerate(a.raters):
        for s in a.raters[i + 1:]:
            x = [data[r][t][v][0] for t in TASKS for v in pool[t]]
            y = [data[s][t][v][0] for t in TASKS for v in pool[t]]
            summary["between_raters"][f"{r}|{s}"] = {"kappa": kappa(x, y), "agree": sum(p == q for p, q in zip(x, y)), "n": len(x)}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "reference_agreement.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with open(a.out / "disagreements.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["task", "variable", "reference_exclude", "reference_category"] + [f"{r}_{c}" for r in a.raters for c in ("exclude", "criterion", "reason")] + ["human_exclude", "human_note"])
        for t in TASKS:
            for v in pool[t]:
                refv = ref.get((TASKS[t], v), 0)
                vals = [data[r][t][v] for r in a.raters]
                if any(x[0] != refv for x in vals) or len({x[0] for x in vals}) > 1:
                    w.writerow([t, v, refv, cat.get((TASKS[t], v), "")] + [c for x in vals for c in x] + ["", ""])
    print(json.dumps({k: summary[k] for k in ("pool_per_task", "between_raters")}, indent=1))
    for r in a.raters:
        print(r, "pooled kappa", summary["raters"][r]["pooled_kappa"])


if __name__ == "__main__":
    main()
