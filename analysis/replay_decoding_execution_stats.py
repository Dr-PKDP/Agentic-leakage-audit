"""Statistics for the review-replay, constrained-decoding, gate-operating-characteristic and execution-check runs.

Reads results/review_replay, results/constrained_decoding, results/gate_operating_characteristics and
results/execution_check together with the archived longer-limit and clarified-instruction runs, and writes
results/replay_decoding_execution_stats.json. No model calls and no participant data.
"""
import collections
import csv
import json
import random
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
SEED = 20261119
BOOT = 5000
STREAMS = ["self_review", "structure_feedback", "evidence_critic", "patch_critic/evidence_guarded"]
PATHS = STREAMS[:3] + ["patch_critic/interface_only", "patch_critic/evidence_guarded"]
CON = "contradicted_contract"


def rows(path):
    with open(path, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def repaired(r):
    return int(r["initial"] == CON and r["final"] == "supported")


def harmful(r):
    return int(r["initial"] == "supported" and r["final"] == CON)


def paired_repair(a_rows, b_rows, paths):
    """Repair of contradicted inputs in two runs over the same inputs, paired by proposal, seed and path."""
    def key(r):
        return (r["proposal_id"], r["seed"], r["path"])
    A = {key(r): r for r in a_rows if r["path"] in paths and r["initial"] == CON}
    B = {key(r): r for r in b_rows if r["path"] in paths and r["initial"] == CON}
    ks = sorted(set(A) & set(B))
    x = [repaired(A[k]) for k in ks]
    y = [repaired(B[k]) for k in ks]
    only_a = sum(1 for i, j in zip(x, y) if i and not j)
    only_b = sum(1 for i, j in zip(x, y) if j and not i)
    ctx = [A[k]["context_id"] for k in ks]
    groups = collections.defaultdict(list)
    for c, i, j in zip(ctx, x, y):
        groups[c].append((i, j))
    names = sorted(groups)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOT):
        pick = [groups[names[rng.randrange(len(names))]] for _ in names]
        flat = [t for g in pick for t in g]
        diffs.append(100 * (sum(i for i, _ in flat) - sum(j for _, j in flat)) / len(flat))
    diffs.sort()
    return {
        "pairs": len(ks), "first": sum(x), "second": sum(y), "only_first": only_a, "only_second": only_b,
        "difference_pp": round(100 * (sum(x) - sum(y)) / len(ks), 1),
        "bootstrap_95": [round(diffs[int(0.025 * BOOT)], 1), round(diffs[int(0.975 * BOOT) - 1], 1)],
        "exact_mcnemar_p": mcnemar(only_a, only_b),
    }


def by_path(rs, paths):
    out = {}
    for p in paths:
        rr = [r for r in rs if r["path"] == p]
        con = [r for r in rr if r["initial"] == CON]
        sup = [r for r in rr if r["initial"] == "supported"]
        out[p] = {
            "repair": [sum(repaired(r) for r in con), len(con)],
            "preserve": [sum(r["final"] == "supported" for r in sup), len(sup)],
            "harmful": sum(harmful(r) for r in sup),
            "no_output": sum(r["status"] != "completed" or r["pipeline"] == "not_evaluated" for r in rr),
        }
    return out


def replay():
    out = {}
    for s in ("core24", "nhanes"):
        full = rows(RES / f"review_replay/q_replay_full_{s}/outcomes.csv")
        cut = rows(RES / f"review_replay/q_replay_t1024_{s}/outcomes.csv")
        plan_cut = json.loads((RES / f"review_replay/q_replay_t1024_{s}/plan.json").read_text())
        source = rows(RES / f"review_limit_2048/{s}/outcomes.csv")
        out[s] = {
            "reviews": plan_cut["replay_counts"],
            "complete_reviews_by_path": by_path(full, PATHS),
            "reviews_cut_to_1024_by_path": by_path(cut, PATHS),
            "pooled_complete_vs_cut": paired_repair(full, cut, STREAMS),
            "pooled_complete_vs_source_run": paired_repair(full, source, STREAMS),
            "failed_units": {"complete": json.loads((RES / f"review_replay/q_replay_full_{s}/run_report.json").read_text())["failed_or_unparseable_units"],
                             "cut": json.loads((RES / f"review_replay/q_replay_t1024_{s}/run_report.json").read_text())["failed_or_unparseable_units"]},
        }
    return out


def constrained():
    out = {}
    sets = {
        "qwen3_8b": ("constrained_decoding/qwen3_8b/q_con_{s}", {"core24": "review_limit_2048_clarified/core24/strict"}),
        "granite_3_3_8b": ("constrained_decoding/granite_3_3_8b/g_con_{s}", {"core24": "granite_clarified/core24/strict", "nhanes": "granite_clarified/nhanes/strict"}),
    }
    for model, (pattern, comparators) in sets.items():
        out[model] = {}
        for s in ("core24", "nhanes"):
            con = rows(RES / (pattern.format(s=s) + "/outcomes.csv"))
            rep = json.loads((RES / (pattern.format(s=s) + "/run_report.json")).read_text())
            entry = {"requests": rep["generation_requests"], "failed_units": rep["failed_or_unparseable_units"],
                     "constrained": by_path(con, PATHS[:3])}
            if s in comparators:
                cmp_rows = rows(RES / comparators[s] / "outcomes.csv")
                entry["clarified_unconstrained"] = by_path(cmp_rows, PATHS[:3])
            out[model][s] = entry
    return out


def model_scale():
    """Qwen3.8-27B (clarified and constrained arms) beside the two 8B models under schema-constrained revision."""
    base = RES / "model_scale/qwen3_27b"
    out = {}
    for s in ("core24", "nhanes"):
        clar = rows(base / f"q27b_clar_{s}/outcomes.csv")
        con = rows(base / f"q27b_con_{s}/outcomes.csv")
        eight = rows(RES / f"constrained_decoding/qwen3_8b/q_con_{s}/outcomes.csv")
        gran = rows(RES / f"constrained_decoding/granite_3_3_8b/g_con_{s}/outcomes.csv")
        full = STREAMS[:3]
        entry = {"requests": {"clarified": json.loads((base / f"q27b_clar_{s}/run_report.json").read_text())["generation_requests"],
                              "constrained": json.loads((base / f"q27b_con_{s}/run_report.json").read_text())["generation_requests"]},
                 "failed_units": {"clarified": json.loads((base / f"q27b_clar_{s}/run_report.json").read_text())["failed_or_unparseable_units"],
                                  "constrained": json.loads((base / f"q27b_con_{s}/run_report.json").read_text())["failed_or_unparseable_units"]},
                 "qwen3_27b_clarified": by_path(clar, PATHS), "qwen3_27b_constrained": by_path(con, PATHS)}
        for tag, other in (("vs_qwen3_8b_constrained", eight), ("vs_granite_constrained", gran)):
            entry[tag] = {"full_proposal_streams": paired_repair(con, other, full)}
        out[s] = entry
    return out


def gate():
    g = json.loads((RES / "gate_operating_characteristics/summary.json").read_text())
    e = rows(RES / "gate_operating_characteristics/edits.csv")
    applicable = [r for r in e if r["ids"] == "applicable_ids"]
    table = {}
    for grp in ("core24", "nhanes"):
        for cls in ("harmful", "neutral_supported", "repair", "neutral_unsupported"):
            rs = [r for r in applicable if r["set"] == grp and r["class"] == cls]
            table[f"{grp}|{cls}"] = {"edits": len(rs), "interface_only_accepts": sum(int(r["A_accepts"]) for r in rs),
                                     "evidence_gate_accepts": sum(int(r["B_accepts"]) for r in rs)}
    harmful_label = [r for r in applicable if r["set"] == "nhanes" and r["class"] == "harmful"]
    kinds = collections.defaultdict(lambda: [0, 0])
    for r in harmful_label:
        k = kinds[r["archetype"]]
        k[0] += 1
        k[1] += int(r["B_accepts"])
    return {"edits": g["edits"], "candidate_artifacts": g["candidate_artifacts"], "agreement": g["agreement"],
            "applicable_ids": table, "by_ids_and_class": g["by_ids_and_class"],
            "label_harmful_by_archetype": {k: {"edits": v[0], "evidence_gate_accepts": v[1]} for k, v in sorted(kinds.items())}}


def execution():
    rs = rows(RES / "execution_check/executed_outcomes.csv")
    ref = rows(RES / "execution_check/reference.csv")
    th = 0.02
    assess = [r for r in rs if r["final_verdict"] in ("supported", CON)]
    for r in assess:
        r["inflated"] = float(r["inflation_final"]) >= th
        r["flagged"] = r["final_verdict"] == CON
    agree = sum(r["inflated"] == r["flagged"] for r in assess)
    seen, distinct = set(), []
    for r in assess:
        k = (r["context_id"], r["input"], r["auc_final"], r["final_verdict"])
        if k not in seen:
            seen.add(k)
            distinct.append(r)
    cross = collections.Counter((r["input"], r["flagged"], r["inflated"]) for r in assess)
    paths = {}
    for p in sorted({r["path"] for r in assess}):
        rr = [r for r in assess if r["path"] == p]
        paths[p] = {"n": len(rr), "inflated": sum(r["inflated"] for r in rr),
                    "mean_inflation": round(sum(float(r["inflation_final"]) for r in rr) / len(rr), 4)}
    pairs = collections.defaultdict(dict)
    for r in assess:
        if r["initial_verdict"] == "supported" and r["path"].startswith("patch_critic/"):
            pairs[(r["arm"], r["context_id"], r["input"], r["seed"])][r["path"]] = r["inflated"]
    both = [v for v in pairs.values() if len(v) == 2]
    task = collections.defaultdict(list)
    for r in ref:
        task[r["task"]].append(float(r["inflation"]))
    return {
        "threshold_auc": th, "final_proposals_scored": len(rs), "assessable": len(assess),
        "agreement": {"rows": [agree, len(assess)], "distinct_artifacts": [sum(r["inflated"] == r["flagged"] for r in distinct), len(distinct)]},
        "cross_tab": {f"{k[0]}|evaluator_{'contradicted' if k[1] else 'supported'}|{'inflated' if k[2] else 'not_inflated'}": v for k, v in sorted(cross.items())},
        "by_path": paths,
        "patch_pairs_supported_start": {"pairs": len(both), "interface_only_inflated": sum(v["patch_critic/interface_only"] for v in both),
                                         "evidence_gate_inflated": sum(v["patch_critic/evidence_guarded"] for v in both)},
        "reference_inflation_by_task": {t: [round(sum(v) / len(v), 3), min(v), max(v)] for t, v in sorted(task.items())},
    }


def main():
    out = {"replay": replay(), "constrained": constrained(), "model_scale": model_scale(), "gate": gate(), "execution": execution()}
    path = RES / "replay_decoding_execution_stats.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
