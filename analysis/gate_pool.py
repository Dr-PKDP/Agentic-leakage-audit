"""Registry of the acceptance-gate comparison, one row per generated patch.

Every condition in which the same generated patch passed through both acceptance gates is listed once.
A condition is one generation run over one context set. Strict scoring is primary, so the normalized
rescoring of the Granite and clarified-instruction runs is excluded from the pool and reported apart;
a run that is only a rescoring of another run contributes no row of its own. A pair enters the pool when
the initial proposal was supported and both gate outcomes are assessable; unevaluable outputs are counted
separately. A harmful edit is a supported initial proposal whose accepted artifact is contradicted.

Output: gate_pool.json with the registry, the pooled counts, the context-level risk difference with a
bootstrap interval, a context-level sign-flip permutation test and the per-context paired differences.

Usage: python analysis/gate_pool.py [--out DIR]
"""
import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CON = "contradicted_contract"

# condition label, context set, experiment, outcome table, patch path prefix
CONDITIONS = [
    ("Experiment 1 (review limit 1,024); Qwen3-8B, original instruction", "core", 1,
     "core_contexts/per_input_outcomes.csv", "patch_critic/"),
    ("Experiment 1 repeat; Qwen3-8B, original instruction", "core", 1,
     "label_contexts/core24_think_off/outcomes.csv", "patch_critic/"),
    ("Experiment 2 (review limit 1,024); Qwen3-8B, original instruction", "label", 2,
     "label_contexts/nhanes_default/outcomes.csv", "patch_critic/"),
    ("Experiment 2 repeat; Qwen3-8B, original instruction", "label", 2,
     "label_contexts/nhanes_think_off/outcomes.csv", "patch_critic/"),
    ("Experiment 3 (review limit 2,048); Qwen3-8B, original instruction", "core", 3,
     "review_limit_2048/core24/outcomes.csv", "patch_critic/"),
    ("Experiment 3 (review limit 2,048); Qwen3-8B, original instruction", "label", 3,
     "review_limit_2048/nhanes/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, original instruction", "core", 4,
     "granite/core24/strict/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, original instruction", "label", 4,
     "granite/nhanes/strict/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, clarified instruction", "core", 4,
     "granite_clarified/core24/strict/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, clarified instruction", "label", 4,
     "granite_clarified/nhanes/strict/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Qwen3-8B, clarified instruction", "core", 4,
     "review_limit_2048_clarified/core24/strict/outcomes.csv", "patch_critic/"),
    ("Experiment 5; Qwen3-8B, no review", "core", 5,
     "direct_revision/core24/outcomes.csv", "direct_patch/"),
    ("Experiment 5; Qwen3-8B, no review", "label", 5,
     "direct_revision/nhanes/outcomes.csv", "direct_patch/"),
    ("Experiment 5; Qwen3-8B, check then revise", "core", 5,
     "check_revision/core24/outcomes.csv", "direct_patch/"),
    ("Experiment 5; Qwen3-8B, check then revise", "label", 5,
     "check_revision/nhanes/outcomes.csv", "direct_patch/"),
    ("Experiment 6; Qwen3-8B, complete saved reviews", "core", 6,
     "review_replay/q_replay_full_core24/outcomes.csv", "patch_critic/"),
    ("Experiment 6; Qwen3-8B, complete saved reviews", "label", 6,
     "review_replay/q_replay_full_nhanes/outcomes.csv", "patch_critic/"),
    ("Experiment 6; Qwen3-8B, reviews cut to 1,024 tokens", "core", 6,
     "review_replay/q_replay_t1024_core24/outcomes.csv", "patch_critic/"),
    ("Experiment 6; Qwen3-8B, reviews cut to 1,024 tokens", "label", 6,
     "review_replay/q_replay_t1024_nhanes/outcomes.csv", "patch_critic/"),
    ("Experiment 10; Qwen3.8-27B, clarified instruction", "core", 10,
     "model_scale/qwen3_27b/q27b_clar_core24/outcomes.csv", "patch_critic/"),
    ("Experiment 10; Qwen3.8-27B, clarified instruction", "label", 10,
     "model_scale/qwen3_27b/q27b_clar_nhanes/outcomes.csv", "patch_critic/"),
    ("Experiment 10; Qwen3.8-27B, constrained revision", "core", 10,
     "model_scale/qwen3_27b/q27b_con_core24/outcomes.csv", "patch_critic/"),
    ("Experiment 10; Qwen3.8-27B, constrained revision", "label", 10,
     "model_scale/qwen3_27b/q27b_con_nhanes/outcomes.csv", "patch_critic/"),
]

# rescorings of a run already listed above, kept out of the pool and reported separately
RESCORINGS = [
    ("Experiment 4; Granite 3.3 8B Instruct, original instruction, normalized", "core",
     "granite/core24/normalized/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, original instruction, normalized", "label",
     "granite/nhanes/normalized/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, clarified instruction, normalized", "core",
     "granite_clarified/core24/normalized/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Granite 3.3 8B Instruct, clarified instruction, normalized", "label",
     "granite_clarified/nhanes/normalized/outcomes.csv", "patch_critic/"),
    ("Experiment 4; Qwen3-8B, clarified instruction, normalized", "core",
     "review_limit_2048_clarified/core24/normalized/outcomes.csv", "patch_critic/"),
]


def pairs_of(table, prefix, initial="supported"):
    """Initial proposals whose patch reached both gates, with each gate's outcome.

    For a supported initial proposal the flag is a harmful edit (the accepted artifact is contradicted);
    for a contradicted one it is a repair (the accepted artifact is supported).
    """
    rows = list(csv.DictReader(open(RES / table, newline="", encoding="utf-8")))
    by_unit = {}
    for r in rows:
        if not r["path"].startswith(prefix) or r["initial"] != initial:
            continue
        key = (r["context_id"], r["proposal_id"], r.get("seed", "42"))
        by_unit.setdefault(key, {})[r["path"].split("/")[1]] = r
    out, unevaluable = [], 0
    bad = (lambda v: v["final"] == CON) if initial == "supported" else (lambda v: v["final"] == "supported")
    for key, g in sorted(by_unit.items()):
        if len(g) != 2:
            continue
        if any(v["pipeline"] != "assessable" for v in g.values()):
            unevaluable += 1
            continue
        out.append((key, bad(g["interface_only"]), bad(g["evidence_guarded"])))
    return out, unevaluable


def bootstrap(by_context, reps, seed):
    keys = sorted(by_context)
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        pick = [by_context[rng.choice(keys)] for _ in keys]
        n = sum(c[0] for c in pick)
        if not n:
            continue
        diffs.append(100 * (sum(c[1] for c in pick) - sum(c[2] for c in pick)) / n)
    diffs.sort()
    return [round(diffs[int(0.025 * len(diffs))], 1), round(diffs[int(0.975 * len(diffs)) - 1], 1)]


def signflip(by_context, reps, seed):
    """Context-level randomization test of no difference between the gates.

    The statistic is the mean over contexts of the within-context difference in harmful-edit rate.
    Under the null the sign of each context's difference is exchangeable, so every assignment of signs
    is enumerated when there are few contexts and sampled otherwise.
    """
    d = [(c[1] - c[2]) / c[0] for c in by_context.values() if c[0]]
    k = len(d)
    obs = abs(sum(d) / k)
    if k <= 20:
        total, hits = 2 ** k, 0
        for m in range(total):
            s = sum(x if (m >> i) & 1 else -x for i, x in enumerate(d))
            hits += abs(s / k) >= obs - 1e-12
        return round(hits / total, 5), total, k
    rng = random.Random(seed)
    hits = sum(abs(sum(x if rng.random() < 0.5 else -x for x in d) / k) >= obs - 1e-12 for _ in range(reps))
    return round((hits + 1) / (reps + 1), 5), reps, k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=RES)
    ap.add_argument("--reps", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()

    registry, by_context = [], {}
    totals = [0, 0, 0, 0]
    for label, cset, exp, table, prefix in CONDITIONS:
        pairs, unevaluable = pairs_of(table, prefix)
        ha = sum(p[1] for p in pairs)
        hb = sum(p[2] for p in pairs)
        registry.append({"condition": label, "context_set": cset, "experiment": exp, "table": table,
                         "paired_supported_inputs": len(pairs), "unevaluable_pairs": unevaluable,
                         "harmful_interface_only": ha, "harmful_evidence_gate": hb})
        totals[0] += len(pairs); totals[1] += ha; totals[2] += hb; totals[3] += unevaluable
        for (ctx, _pid, _seed), a_bad, b_bad in pairs:
            c = by_context.setdefault(ctx, [0, 0, 0])
            c[0] += 1; c[1] += a_bad; c[2] += b_bad

    rescored = []
    for label, cset, table, prefix in RESCORINGS:
        pairs, unevaluable = pairs_of(table, prefix)
        rescored.append({"condition": label, "context_set": cset, "table": table,
                         "paired_supported_inputs": len(pairs), "unevaluable_pairs": unevaluable,
                         "harmful_interface_only": sum(p[1] for p in pairs),
                         "harmful_evidence_gate": sum(p[2] for p in pairs)})

    # the repair side of the same pool: contradicted initial proposals whose patch reached both gates
    rep = [0, 0, 0, 0, 0]
    for _label, _cset, _exp, table, prefix in CONDITIONS:
        pairs, unevaluable = pairs_of(table, prefix, initial=CON)
        rep[0] += len(pairs); rep[3] += unevaluable
        rep[1] += sum(p[1] for p in pairs); rep[2] += sum(p[2] for p in pairs)
        rep[4] += sum(1 for p in pairs if p[1] != p[2])

    n, ha, hb, unev = totals
    discordant_pairs = 0
    gate_b_worse = 0
    for _label, _cset, _exp, table, prefix in CONDITIONS:
        pairs, _u = pairs_of(table, prefix)
        discordant_pairs += sum(1 for p in pairs if p[1] != p[2])
        gate_b_worse += sum(1 for p in pairs if p[2] and not p[1])
    discordant = sum(1 for c in by_context.values() if c[1] != c[2])
    p, draws, clusters = signflip(by_context, a.reps, a.seed)
    summary = {
        "conditions": len(registry), "paired_supported_inputs": n, "unevaluable_pairs_excluded": unev,
        "harmful_interface_only": ha, "harmful_evidence_gate": hb,
        "risk_difference_pp_pooled": round(100 * (ha - hb) / n, 1),
        "discordant_pairs": discordant_pairs, "pairs_where_evidence_gate_worse": gate_b_worse,
        "contexts": len(by_context), "contexts_with_discordance": discordant,
        "repair_side": {"paired_contradicted_inputs": rep[0], "unevaluable_pairs_excluded": rep[3],
                        "repairs_interface_only": rep[1], "repairs_evidence_gate": rep[2],
                        "discordant_pairs": rep[4]},
        "context_level_mean_difference_pp": round(100 * sum((c[1] - c[2]) / c[0] for c in by_context.values()) / len(by_context), 1),
        "context_bootstrap_95": bootstrap(by_context, a.reps, a.seed),
        "bootstrap_resamples": a.reps, "bootstrap_seed": a.seed,
        "signflip_p": p, "signflip_assignments": draws, "signflip_clusters": clusters,
    }
    pair_rows = []
    for label, cset, _exp, table, prefix in CONDITIONS:
        for (ctx, pid, seed), a_bad, b_bad in pairs_of(table, prefix)[0]:
            pair_rows.append([ctx, pid, seed, cset, label, int(a_bad), int(b_bad)])

    out = {"summary": summary, "registry": registry, "rescorings_excluded": rescored,
           "per_context": {k: {"pairs": v[0], "harmful_interface_only": v[1], "harmful_evidence_gate": v[2]}
                           for k, v in sorted(by_context.items())},
           "pair_columns": ["context_id", "proposal_id", "seed", "context_set", "condition",
                            "harmful_interface_only", "harmful_evidence_gate"],
           "pairs": pair_rows}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "gate_pool.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
