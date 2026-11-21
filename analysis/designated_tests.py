"""The five designated hypothesis-level tests, with context-level inference and a Holm adjustment.

Contexts are the unit of inference, because the two initial proposals of a context, the seeds of an input
and the paths applied to it are not independent. Each contrast is therefore estimated as the mean over
contexts of the within-context difference in the outcome rate, with a percentile interval from a bootstrap
that resamples contexts and a randomization test that flips the sign of each context's difference. A
generalized estimating equation with an identity link, binomial variance and an exchangeable working
correlation clustered on context is fitted to the same rows for comparison. The Holm procedure is applied
across the five.

The tests were selected after the responses of the later experiments were available, so they are
multiplicity-adjusted hypothesis-level analyses and not a prespecified confirmatory family.

Output: designated_tests.json

Usage: python analysis/designated_tests.py [--out DIR]
"""
import argparse
import csv
import json
import random
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CON = "contradicted_contract"

E1_CORE = "core_contexts/per_input_outcomes.csv"
E2_LABEL = "label_contexts/nhanes_default/outcomes.csv"
E3_CORE = "review_limit_2048/core24/outcomes.csv"
E3_LABEL = "review_limit_2048/nhanes/outcomes.csv"
E5_CORE = "direct_revision/core24/outcomes.csv"
STREAMS = ["self_review", "structure_feedback", "evidence_critic", "patch_critic/evidence_guarded"]


def read(table):
    return list(csv.DictReader(open(RES / table, newline="", encoding="utf-8")))


def rows_for(table, paths, initial, outcome, family=None):
    """Rows of (context, 1 if the proposal reached the outcome else 0) for the given paths."""
    out = []
    for r in read(table):
        if r["path"] not in paths or r["initial"] != initial:
            continue
        if family and r.get("family") != family:
            continue
        out.append((r["context_id"], int(r["final"] == outcome)))
    return out


def per_context(a_rows, b_rows):
    """Within-context difference in the outcome rate, for contexts present in both arms."""
    def rate(rows):
        agg = {}
        for ctx, y in rows:
            c = agg.setdefault(ctx, [0, 0])
            c[0] += 1
            c[1] += y
        return {k: v[1] / v[0] for k, v in agg.items()}, {k: v[0] for k, v in agg.items()}

    ra, na = rate(a_rows)
    rb, nb = rate(b_rows)
    keys = sorted(set(ra) & set(rb))
    return [(k, ra[k] - rb[k], na[k], nb[k]) for k in keys]


def bootstrap(diffs, reps, seed):
    rng = random.Random(seed)
    vals = [d[1] for d in diffs]
    draws = sorted(100 * sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(reps))
    return [round(draws[int(0.025 * reps)], 1), round(draws[int(0.975 * reps) - 1], 1)]


def signflip(diffs, reps, seed):
    d = [x[1] for x in diffs]
    k = len(d)
    obs = abs(sum(d) / k)
    if k <= 20:
        total = 2 ** k
        hits = sum(abs(sum(x if (m >> i) & 1 else -x for i, x in enumerate(d)) / k) >= obs - 1e-12
                   for m in range(total))
        return round(hits / total, 5), total
    rng = random.Random(seed)
    hits = sum(abs(sum(x if rng.random() < 0.5 else -x for x in d) / k) >= obs - 1e-12 for _ in range(reps))
    return round((hits + 1) / (reps + 1), 5), reps


def gee(a_rows, b_rows):
    """Risk difference from a GEE with an identity link and an exchangeable correlation on context."""
    try:
        import numpy as np
        import statsmodels.api as sm
    except ImportError:
        return None
    keys = {c for c, _ in a_rows} & {c for c, _ in b_rows}
    y, x, g = [], [], []
    for arm, rows in ((1, a_rows), (0, b_rows)):
        for ctx, val in rows:
            if ctx in keys:
                y.append(val); x.append(arm); g.append(ctx)
    idx = {c: i for i, c in enumerate(sorted(set(g)))}
    X = sm.add_constant(np.asarray(x, float))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fam = sm.families.Binomial(link=sm.families.links.Identity())
            m = sm.GEE(np.asarray(y, float), X, groups=np.asarray([idx[c] for c in g]),
                       family=fam, cov_struct=sm.cov_struct.Exchangeable()).fit(maxiter=200)
        lo, hi = m.conf_int()[1]
        return {"risk_difference_pp": round(100 * m.params[1], 1),
                "ci95_pp": [round(100 * lo, 1), round(100 * hi, 1)],
                "clusters": len(idx), "converged": bool(m.converged)}
    except Exception as exc:  # a non-canonical link can fail on sparse tables
        return {"error": type(exc).__name__}


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0.0] * len(ps)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (len(ps) - rank) * ps[i])
        adj[i] = min(1.0, round(run, 5))
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=RES)
    ap.add_argument("--reps", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()

    tests = []

    # H1  explicit checking: a critic review against revision with no review (core contexts)
    tests.append(("H1", "Repair with a critic review against revision without one (self-review, core contexts)",
                  rows_for(E3_CORE, {"self_review"}, CON, "supported"),
                  rows_for(E5_CORE, {"direct_full"}, CON, "supported")))

    # H2  revision format: a field-level patch against a complete proposal, permissions family
    tests.append(("H2", "Repair by patch against repair by full proposal, permissions family (F05, core contexts)",
                  rows_for(E3_CORE, {"patch_critic/evidence_guarded"}, CON, "supported", family="F05"),
                  rows_for(E3_CORE, {"self_review"}, CON, "supported", family="F05")))

    # H3  acceptance gates: the same generated patch under both gates, every condition (see gate_pool.py)
    pool = json.loads((RES / "gate_pool.json").read_text(encoding="utf-8"))
    h3 = [(k, v["harmful_interface_only"] / v["pairs"] - v["harmful_evidence_gate"] / v["pairs"], v["pairs"], v["pairs"])
          for k, v in pool["per_context"].items()]

    # H4  model critique against fixed rules: the evidence critic against the name-prefix baseline
    tests.append(("H4", "Repair by the evidence critic against the name-prefix baseline (label contexts)",
                  rows_for(E3_LABEL, {"evidence_critic"}, CON, "supported"),
                  rows_for(E3_LABEL, {"prefix_rule_reviser"}, CON, "supported")))

    # H5  review budget: a review limit of 2,048 tokens against 1,024, pooled over the four streams
    tests.append(("H5", "Repair at a review limit of 2,048 tokens against 1,024 (label contexts, four streams)",
                  rows_for(E3_LABEL, set(STREAMS), CON, "supported"),
                  rows_for(E2_LABEL, set(STREAMS), CON, "supported")))

    results = []
    for key, name, arm_a, arm_b in tests:
        d = per_context(arm_a, arm_b)
        p, draws = signflip(d, a.reps, a.seed)
        results.append({
            "hypothesis": key, "contrast": name, "contexts": len(d),
            "rows_first_condition": len(arm_a), "rows_second_condition": len(arm_b),
            "mean_difference_pp": round(100 * sum(x[1] for x in d) / len(d), 1),
            "context_bootstrap_95": bootstrap(d, a.reps, a.seed),
            "contexts_favoring_first": sum(1 for x in d if x[1] > 0),
            "contexts_favoring_second": sum(1 for x in d if x[1] < 0),
            "randomization_p": p, "randomization_assignments": draws,
            "gee": gee(arm_a, arm_b),
        })

    s = pool["summary"]
    h3p, h3draws = signflip(h3, a.reps, a.seed)
    results.insert(2, {
        "hypothesis": "H3",
        "contrast": "Harmful edits under the interface-only gate against the evidence gate (every condition)",
        "contexts": len(h3), "rows_first_condition": s["paired_supported_inputs"],
        "rows_second_condition": s["paired_supported_inputs"],
        "mean_difference_pp": s["context_level_mean_difference_pp"],
        "context_bootstrap_95": s["context_bootstrap_95"],
        "contexts_favoring_first": sum(1 for x in h3 if x[1] > 0),
        "contexts_favoring_second": sum(1 for x in h3 if x[1] < 0),
        "randomization_p": h3p, "randomization_assignments": h3draws,
        "gee": gee([(r[0], r[5]) for r in pool["pairs"]], [(r[0], r[6]) for r in pool["pairs"]]),
    })

    adj = holm([r["randomization_p"] for r in results])
    for r, v in zip(results, adj):
        r["holm_adjusted_p"] = v

    out = {"note": ("Selected after the responses of the later experiments were available; "
                    "multiplicity-adjusted hypothesis-level analyses, not a prespecified confirmatory family."),
           "bootstrap_resamples": a.reps, "bootstrap_seed": a.seed, "tests": results}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "designated_tests.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['hypothesis']}  {r['mean_difference_pp']:+6.1f} pp  "
              f"[{r['context_bootstrap_95'][0]}, {r['context_bootstrap_95'][1]}]  "
              f"k={r['contexts']:3d}  p={r['randomization_p']:<9} holm={r['holm_adjusted_p']:<9} "
              f"gee={r['gee']}")


if __name__ == "__main__":
    main()
