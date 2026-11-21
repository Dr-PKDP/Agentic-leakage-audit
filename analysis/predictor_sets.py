"""Traceability of the executed check: how far an executed row can be joined to its predictor set.

The executed outcome table records a verdict and an AUC for every scored proposal but not the predictor
names it selected. It also enumerates more than one row for some units, because an arm label covers
repeated scoring views and sub-runs, so (model, arm, context, input, path, seed) is not a unique key.
This script quantifies both limits:

1. How many executed rows share a key, and what the row-level agreement becomes when each key is
   collapsed to one row. The collapse is reported under three selection rules, so the reader can see
   that the figure does not depend on which row is kept.
2. For the one arm whose per-unit final artifacts are archived, how many artifacts can be joined to an
   unambiguous executed row, and what the agreement is over distinct predictor sets in that subset.

The subset in (2) is small and is a provenance check, not a result. Recording the final artifact of
every unit is a reporting change for later runs.

Output: predictor_sets.json

Usage: python analysis/predictor_sets.py [--out DIR]
"""
import argparse
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CON = "contradicted_contract"
THRESHOLD = 0.02
INPUT_OF = {"supported": "valid_or_conservative", CON: "counterpart"}
ARM = ("p6-granite-8b", "nhanes_review2048")
MANIFEST = "granite/nhanes/final_artifacts.csv"


def rows(path):
    with (RES / path).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def agrees(r):
    return (float(r["inflation_final"]) >= THRESHOLD) == (r["final_verdict"] == CON)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=RES)
    a = ap.parse_args()

    executed = rows("execution_check/executed_outcomes.csv")
    assessable = [r for r in executed if r["final_verdict"] in ("supported", CON)]
    key = lambda r: (r["model"], r["arm"], r["context_id"], r["input"], r["path"], r["seed"])

    groups = collections.defaultdict(list)
    for r in assessable:
        groups[key(r)].append(r)
    picks = {"first": lambda v: v[0], "last": lambda v: v[-1],
             "least_agreeing": lambda v: min(v, key=agrees)}
    collapsed = {name: [sum(agrees(f(v)) for v in groups.values()), len(groups)]
                 for name, f in picks.items()}

    per_arm = {}
    by_arm = collections.defaultdict(list)
    for r in executed:
        by_arm[(r["model"], r["arm"])].append(r)
    for (model, arm), v in sorted(by_arm.items()):
        c = collections.Counter((r["context_id"], r["input"], r["path"], r["seed"]) for r in v)
        per_arm[f"{model}|{arm}"] = {"rows": len(v), "distinct_keys": len(c),
                                     "keys_with_more_than_one_row": sum(1 for n in c.values() if n > 1)}

    # the one arm with archived final artifacts, restricted to unambiguous executed rows
    model, arm = ARM
    arm_rows = [r for r in executed if r["model"] == model and r["arm"] == arm]
    counts = collections.Counter((r["context_id"], r["input"], r["path"], r["seed"]) for r in arm_rows)
    unique = {}
    for r in arm_rows:
        k = (r["context_id"], r["input"], r["path"], r["seed"])
        if counts[k] == 1:
            unique[k] = r

    sets = collections.defaultdict(list)
    joined = ambiguous = unscored = 0
    for r in rows(MANIFEST):
        if not r["selected"]:
            continue
        k = (r["context_id"], INPUT_OF.get(r["initial_verdict"]), r["path"], r["seed"])
        e = unique.get(k)
        if e is None:
            ambiguous += 1
            continue
        if e["inflation_final"] == "":
            unscored += 1
            continue
        joined += 1
        sets[(r["context_id"], r["selected"])].append(
            (float(e["inflation_final"]) >= THRESHOLD, e["final_verdict"] == CON))

    pair_rows = [x for v in sets.values() for x in v]
    out = {
        "note": ("The executed table does not record predictor names and its key is not unique, so a "
                 "set-level denominator cannot be formed for the whole pool. Both limits are quantified "
                 "here; the joined subset is a provenance check and not a result."),
        "threshold_auc": THRESHOLD,
        "rows_as_published": [sum(map(agrees, assessable)), len(assessable)],
        "distinct_units_among_assessable_rows": len(groups),
        "agreement_after_collapsing_each_key": collapsed,
        "rows_and_keys_by_arm": per_arm,
        "archived_artifact_arm": {
            "model": model, "arm": arm, "manifest": MANIFEST,
            "artifacts_joined_to_an_unambiguous_row": joined,
            "artifacts_skipped_ambiguous_key": ambiguous,
            "artifacts_skipped_no_fitted_auc": unscored,
            "distinct_predictor_sets": len(sets),
            "set_level_agreement": [sum(1 for v in sets.values() if all(i == f for i, f in v)), len(sets)],
            "row_level_agreement": [sum(1 for i, f in pair_rows if i == f), len(pair_rows)],
            "sets_with_inconsistent_rows": sum(1 for v in sets.values() if len(set(v)) > 1),
        },
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "predictor_sets.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows_and_keys_by_arm"}, indent=1))


if __name__ == "__main__":
    main()
