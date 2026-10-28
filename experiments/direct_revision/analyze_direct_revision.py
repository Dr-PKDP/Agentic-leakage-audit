"""Offline analysis of a direct-revision run, paired with the 2,048-token critic-reviser results (Experiment 3).

Usage: python analyze_direct_revision.py --plan-dir PLAN --run-dir RUN --out-dir NEW_DIR [--reference results/review_limit_2048/<set>/outcomes.csv]
Writes outcomes.csv and summary.json. Standard library only; no network and no model calls.
Paired contrasts compare each direct-revision arm with the critic-reviser paths that share its revision format
on the same inputs and seeds (exact McNemar test; context-level bootstrap interval for the difference in repair rate).
"""
import argparse, collections, csv, json, random, statistics, sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "core_contexts")); sys.path.insert(0, str(HERE.parent / "label_contexts"))
import p6_direct_revision as d
v4, ext = d.v4, d.ext
T, F = v4.T, v4.F
PAIRS = {"direct_full": ["self_review", "structure_feedback", "evidence_critic"],
         "direct_patch/interface_only": ["patch_critic/interface_only"], "direct_patch/evidence_guarded": ["patch_critic/evidence_guarded"]}


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-dir", type=Path, required=True); ap.add_argument("--run-dir", type=Path, required=True); ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--reference", type=Path, default=None, help="outcomes.csv of the matching Experiment 3 arm")
    a = ap.parse_args()
    plan = json.loads((a.plan_dir / "plan.json").read_text()); jobs = {j["unit"]: j for j in json.loads((a.plan_dir / "jobs.json").read_text())}
    items = ext.context_items(plan["context_set"]); valid = {i["public"]["context_id"]: i["valid_or_conservative"] for i in items}
    rows = []
    for f in sorted(a.run_dir.glob("*__*.json")):
        rec = json.loads(f.read_text()); j = jobs[rec["unit"]]; c = j["context"]
        base = {"proposal_id": j["proposal_id"], "context_id": c["context_id"], "family": c["family"], "archetype": c["archetype"], "seed": j["seed"],
                "initial": rec["initial_assessment"]["verdict"], "status": rec["status"]}

        def row(path, assess, artifact, action=""):
            r = dict(base); r.update(unit=rec["unit"].replace(j["arm"], path.split("/")[0]), path=path, final=assess.get("verdict", "not_evaluated"),
                                     pipeline=assess.get("pipeline", "not_evaluated"), action=action)
            r["retained_fraction"] = round(ext.retained_fraction(c, artifact, valid[c["context_id"]]), 3) if c["family"] == "F07" and isinstance(artifact, dict) else ""
            return r
        if j["arm"] == "direct_patch":
            outs = rec.get("paired_patch_paths", {}).get("outputs", {})
            for pn in ("interface_only", "evidence_guarded"):
                o = outs.get(pn, {}); act = o.get("action", {})
                rows.append(row("direct_patch/" + pn, o.get("accepted_artifact_assessment", {}), act.get("artifact"), act.get("path", "") + (":" + ",".join(act.get("reasons", [])) if act.get("reasons") else "")))
        else:
            rows.append(row("direct_full", rec.get("final_assessment", {}), rec.get("final_artifact")))
    a.out_dir.mkdir(parents=True, exist_ok=False)
    with (a.out_dir / "outcomes.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def tally(rs):
        rep = [r for r in rs if r["initial"] == F]; pre = [r for r in rs if r["initial"] == T]
        rf = [float(r["retained_fraction"]) for r in rs if r["retained_fraction"] != ""]
        return {"repair": [sum(r["final"] == T for r in rep), len(rep)], "preserve": [sum(r["final"] == T for r in pre), len(pre)],
                "harmful": sum(r["final"] == F for r in pre), "no_output": sum(r["pipeline"] in ("not_evaluated", "schema_failure") for r in rs),
                "unchanged_input": sum(r["action"].startswith("no_op") for r in rs), "mean_retained_fraction": round(statistics.mean(rf), 3) if rf else None}
    paths = list(PAIRS)
    summary = {"arm": plan["arm"], "model": plan["model"], "seeds": plan["seeds"], "by_path": {p: tally([r for r in rows if r["path"] == p]) for p in paths},
               "permissions_family_repair": {p: tally([r for r in rows if r["path"] == p and r["family"] == "F05"])["repair"] for p in paths}}
    if a.reference:
        ref = [r for r in csv.DictReader(a.reference.open())]; R = {(r["unit"], r["path"]): r for r in ref}
        D = {(r["unit"], r["path"]): r for r in rows}; contrasts = {}
        for dp, refs in PAIRS.items():
            for rp in refs:
                for init, key in ((F, "repair"), (T, "preserve")):
                    ks = []
                    for (u, p), r in D.items():
                        if p != dp or r["initial"] != init: continue
                        ru = u.replace(dp.split("/")[0], rp.split("/")[0]);
                        if (ru, rp) in R: ks.append((u, ru))
                    both = lambda s: s == T
                    only_direct = sum(both(D[(u, dp)]["final"]) and not both(R[(ru, rp)]["final"]) for u, ru in ks)
                    only_crit = sum(both(R[(ru, rp)]["final"]) and not both(D[(u, dp)]["final"]) for u, ru in ks)
                    byctx = collections.defaultdict(lambda: [0, 0, 0])
                    for u, ru in ks:
                        cx = D[(u, dp)]["context_id"]; byctx[cx][0] += both(D[(u, dp)]["final"]); byctx[cx][1] += both(R[(ru, rp)]["final"]); byctx[cx][2] += 1
                    cxs = list(byctx); diffs = []
                    rng = random.Random(20261029)
                    for _ in range(5000):
                        s = [byctx[rng.choice(cxs)] for _ in cxs]; n = sum(x[2] for x in s)
                        diffs.append(100 * (sum(x[0] for x in s) - sum(x[1] for x in s)) / n if n else 0)
                    diffs.sort()
                    contrasts[f"{dp} vs {rp} ({key})"] = {"pairs": len(ks), "direct_only": only_direct, "critic_workflow_only": only_crit, "exact_mcnemar_p": round(mcnemar(only_direct, only_crit), 4),
                                                        "difference_points_direct_minus_critic": round(100 * (only_direct - only_crit) / len(ks), 1) if ks else None,
                                                        "context_bootstrap_95": [round(diffs[125], 1), round(diffs[4874], 1)]}
        summary["paired_vs_critic_reviser"] = contrasts
    ev = [json.loads(s) for s in (a.run_dir / "requests.jsonl").read_text().splitlines() if s.strip()]
    fin = collections.Counter(e["response"]["choices"][0]["finish_reason"] for e in ev if e.get("status") == "completed")
    summary["requests"] = {"n": len(ev), "errors": sum(e.get("status") != "completed" for e in ev), "finish_reasons": dict(fin),
                           "median_completion_tokens": statistics.median(e["response"]["usage"]["completion_tokens"] for e in ev if e.get("status") == "completed")}
    (a.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"by_path": summary["by_path"], "permissions_family_repair": summary["permissions_family_repair"], "requests": summary["requests"]}, indent=2))


if __name__ == "__main__":
    main()
