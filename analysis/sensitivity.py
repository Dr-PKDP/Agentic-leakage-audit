"""Sensitivity analyses of the principal run, computed offline from the archived records.

Writes results/principal_v0_4/sensitivity.json. No model calls and no new generation.

A. Outcomes stratified by whether the review stopped at the output limit.
B. Feature selections of the availability and target-dependency families compared with the
   deterministic rule reference, to separate repairs that keep the valid features from repairs
   that only shrink the selection.
C. Paired contrasts between workflow paths with exact McNemar tests and context-level bootstrap
   intervals for the difference.
D. Repair and preservation rates with each constraint family left out in turn.
"""

import json
import math
import random
from pathlib import Path

import rule_reference

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "experiments/principal_v0_4"
SUPPORTED, CONTRADICTED = "supported", "contradicted_contract"
PATHS = [
    "self_review",
    "structure_feedback",
    "evidence_critic",
    "patch_critic/interface_only",
    "patch_critic/evidence_guarded",
]
BOOTSTRAP = 5000
SEED = 20261027


def load():
    jobs = json.loads((RUN / "jobs.json").read_text())
    units = json.loads((RUN / "units.json").read_text())
    ledger = json.loads((RUN / "request_ledger.json").read_text())
    refs = {
        r["proposal_id"]: r["assessment"]["verdict"]
        for r in json.loads((RUN / "references.json").read_text())
    }
    finish = {
        (e["unit"], e["stage"]): e["response"]["choices"][0]["finish_reason"]
        for e in ledger
    }
    rows = []
    for j in jobs:
        u = units[j["unit"]]
        c = j["context"]
        if j["stream"] == "patch_critic":
            outs = u.get("paired_patch_paths", {}).get("outputs", {})
            variants = [
                (
                    "patch_critic/" + g,
                    outs.get(g, {}).get("accepted_artifact_assessment", {}),
                    outs.get(g, {}).get("action", {}).get("artifact"),
                )
                for g in ("interface_only", "evidence_guarded")
            ]
        else:
            variants = [
                (j["stream"], u.get("final_assessment", {}), u.get("final_artifact"))
            ]
        for path, assessment, artifact in variants:
            rows.append(
                {
                    "input": j["proposal_id"],
                    "context": c["context_id"],
                    "family": c["family"],
                    "path": path,
                    "initial": refs[j["proposal_id"]],
                    "final": assessment.get("verdict", "not_evaluated"),
                    "truncated": finish[(j["unit"], "review")] == "length",
                    "artifact": artifact,
                    "ctx": c,
                }
            )
    return rows


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (centre - half), 1), round(100 * (centre + half), 1)]


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact p for the table [[a, b], [c, d]]."""
    n, r1, c1 = a + b + c + d, a + b, a + c
    prob = lambda x: math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    observed = prob(a)
    return sum(
        prob(x)
        for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1)
        if prob(x) <= observed + 1e-12
    )


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def rate(rows, initial, predicate):
    sel = [r for r in rows if r["initial"] == initial]
    return [sum(predicate(r) for r in sel), len(sel)]


def stratified(rows):
    out = {}
    for path in PATHS:
        pr = [r for r in rows if r["path"] == path]
        entry = {}
        for label, flag in (("review_truncated", True), ("review_complete", False)):
            sub = [r for r in pr if r["truncated"] is flag]
            entry[label] = {
                "inputs": len(sub),
                "repaired": rate(sub, CONTRADICTED, lambda r: r["final"] == SUPPORTED),
                "preserved": rate(sub, SUPPORTED, lambda r: r["final"] == SUPPORTED),
            }
        out[path] = entry
    gate_b = [r for r in rows if r["path"] != "patch_critic/interface_only"]
    pooled = {}
    for label, flag in (("review_truncated", True), ("review_complete", False)):
        sub = [r for r in gate_b if r["truncated"] is flag]
        pooled[label] = {
            "inputs": len(sub),
            "repaired": rate(sub, CONTRADICTED, lambda r: r["final"] == SUPPORTED),
            "preserved": rate(sub, SUPPORTED, lambda r: r["final"] == SUPPORTED),
        }
    # Repair rate among contradicted inputs, review truncated versus complete, pooled over the four streams.
    contradicted = [r for r in gate_b if r["initial"] == CONTRADICTED]
    t = [r for r in contradicted if r["truncated"]]
    c = [r for r in contradicted if not r["truncated"]]
    ok = lambda rs: sum(r["final"] == SUPPORTED for r in rs)
    contexts = sorted({r["context"] for r in contradicted})
    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOTSTRAP):
        draw = [rng.choice(contexts) for _ in contexts]
        sub = [r for ctx in draw for r in contradicted if r["context"] == ctx]
        tt = [r for r in sub if r["truncated"]]
        cc = [r for r in sub if not r["truncated"]]
        if tt and cc:
            diffs.append(ok(cc) / len(cc) - ok(tt) / len(tt))
    diffs.sort()
    pooled["repair_complete_minus_truncated"] = {
        "difference_pp": round(100 * (ok(c) / len(c) - ok(t) / len(t)), 1),
        "bootstrap_95_pp": [
            round(100 * diffs[int(0.025 * len(diffs))], 1),
            round(100 * diffs[int(0.975 * len(diffs)) - 1], 1),
        ],
        "fisher_exact_p_descriptive": round(
            fisher_exact(ok(t), len(t) - ok(t), ok(c), len(c) - ok(c)), 4
        ),
        "truncated_share_of_reviews_by_initial_state": {
            "contradicted": round(
                sum(r["truncated"] for r in contradicted) / len(contradicted), 3
            ),
            "supported": round(
                sum(r["truncated"] for r in gate_b if r["initial"] == SUPPORTED)
                / sum(r["initial"] == SUPPORTED for r in gate_b),
                3,
            ),
        },
    }
    out["pooled_four_streams_gate_b"] = pooled
    return out


def selection_quality(rows):
    reference = {}
    out = {}
    for path in PATHS:
        entry = {
            "repaired_inputs": 0,
            "repaired_exact_reference_selection": 0,
            "repaired_empty_selection": 0,
            "repaired_mean_coverage": None,
            "preserved_inputs": 0,
            "preserved_exact_reference_selection": 0,
            "preserved_mean_coverage": None,
        }
        cov_r, cov_p = [], []
        for r in rows:
            if (
                r["path"] != path
                or r["family"] not in ("F01", "F02")
                or r["final"] != SUPPORTED
                or not isinstance(r["artifact"], dict)
            ):
                continue
            ref = reference.setdefault(
                r["context"], set(rule_reference.propose(r["ctx"])["selected"])
            )
            sel = set(r["artifact"].get("selected", []))
            coverage = len(sel & ref) / len(ref) if ref else 1.0
            if r["initial"] == CONTRADICTED:
                entry["repaired_inputs"] += 1
                entry["repaired_exact_reference_selection"] += sel == ref
                entry["repaired_empty_selection"] += not sel
                cov_r.append(coverage)
            elif r["initial"] == SUPPORTED:
                entry["preserved_inputs"] += 1
                entry["preserved_exact_reference_selection"] += sel == ref
                cov_p.append(coverage)
        entry["repaired_mean_coverage"] = (
            round(sum(cov_r) / len(cov_r), 3) if cov_r else None
        )
        entry["preserved_mean_coverage"] = (
            round(sum(cov_p) / len(cov_p), 3) if cov_p else None
        )
        out[path] = entry
    n_ref = {c: len(v) for c, v in reference.items()}
    out["reference_selection_sizes"] = n_ref
    return out


def paired_contrasts(rows):
    by = {p: {r["input"]: r for r in rows if r["path"] == p} for p in PATHS}
    ctx_of = {r["input"]: r["context"] for r in rows}
    contexts = sorted(set(ctx_of.values()))
    inputs_in = {c: [i for i in by[PATHS[0]] if ctx_of[i] == c] for c in contexts}
    rng = random.Random(SEED)
    draws = [[rng.choice(contexts) for _ in contexts] for _ in range(BOOTSTRAP)]
    base = "patch_critic/evidence_guarded"
    contrasts = {}
    for other in PATHS:
        if other == base:
            continue
        entry = {}
        for name, initial in (
            ("repair", CONTRADICTED),
            ("preservation", SUPPORTED),
            ("all_inputs", None),
        ):
            ids = [
                i
                for i in by[base]
                if initial is None or by[base][i]["initial"] == initial
            ]
            win = lambda i, p: by[p][i]["final"] == SUPPORTED
            b = sum(win(i, base) and not win(i, other) for i in ids)
            c = sum(win(i, other) and not win(i, base) for i in ids)
            n = len(ids)
            diffs = []
            for draw in draws:
                sel = [i for ctx in draw for i in inputs_in[ctx] if i in set(ids)]
                if sel:
                    diffs.append(
                        sum(win(i, base) for i in sel) / len(sel)
                        - sum(win(i, other) for i in sel) / len(sel)
                    )
            diffs.sort()
            lo, hi = diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]
            contrasts_k = {
                "inputs": n,
                "patch_gate_b_only": b,
                "other_only": c,
                "difference_pp": round(
                    100
                    * (sum(win(i, base) for i in ids) - sum(win(i, other) for i in ids))
                    / n,
                    1,
                ),
                "bootstrap_95_pp": [round(100 * lo, 1), round(100 * hi, 1)],
                "mcnemar_exact_p": round(mcnemar_exact(b, c), 4),
            }
            entry[name] = contrasts_k
        contrasts[other] = entry
    return {
        "reference_path": base,
        "contrasts": contrasts,
        "bootstrap_resamples": BOOTSTRAP,
        "seed": SEED,
    }


def leave_one_family_out(rows):
    out = {}
    for fam in sorted({r["family"] for r in rows}):
        sub = [r for r in rows if r["family"] != fam]
        out[fam] = {
            p: {
                "repaired": rate(
                    [r for r in sub if r["path"] == p],
                    CONTRADICTED,
                    lambda r: r["final"] == SUPPORTED,
                ),
                "preserved": rate(
                    [r for r in sub if r["path"] == p],
                    SUPPORTED,
                    lambda r: r["final"] == SUPPORTED,
                ),
            }
            for p in PATHS
        }
    return out


def main():
    rows = load()
    result = {
        "stratified_by_review_truncation": stratified(rows),
        "selection_quality_F01_F02": selection_quality(rows),
        "paired_contrasts": paired_contrasts(rows),
        "leave_one_family_out": leave_one_family_out(rows),
    }
    out = ROOT / "results/principal_v0_4/sensitivity.json"
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "stratified_by_review_truncation",
                    "selection_quality_F01_F02",
                    "paired_contrasts",
                )
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
