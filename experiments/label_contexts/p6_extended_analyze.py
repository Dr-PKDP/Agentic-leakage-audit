"""Offline analysis of one P6 v0.5 run (standard library only; no network, no model calls).
Usage: python p6_extended_analyze.py --plan-dir PLAN --run-dir RUN --out-dir NEW_DIR
Writes outcomes.csv, summary.json and prints a compact summary. Original run files are not modified."""
import argparse, collections, csv, json, statistics
from pathlib import Path
import p6_extended_v0_5 as x

v4 = x.v4
PATHS = ["self_review", "structure_feedback", "evidence_critic", "patch_critic/interface_only", "patch_critic/evidence_guarded"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-dir", type=Path, required=True); ap.add_argument("--run-dir", type=Path, required=True); ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    plan = json.loads((a.plan_dir / "plan.json").read_text()); jobs = {j["unit"]: j for j in json.loads((a.plan_dir / "jobs.json").read_text())}
    items = x.context_items(plan["context_set"]); valid = {i["public"]["context_id"]: i["valid_or_conservative"] for i in items}
    rows = []
    for f in sorted(a.run_dir.glob("*__*.json")):
        rec = json.loads(f.read_text()); j = jobs[rec["unit"]]; c = j["context"]; fam = c["family"]
        base = {"unit": rec["unit"], "proposal_id": j["proposal_id"], "context_id": c["context_id"], "rule_id": c["rule_id"], "family": fam,
                "archetype": c["archetype"], "seed": j["seed"], "initial": rec["initial_assessment"]["verdict"], "status": rec["status"]}
        def row(path, assess, artifact, action=""):
            r = dict(base); r.update(path=path, final=assess.get("verdict", "not_evaluated"), pipeline=assess.get("pipeline", "not_evaluated"), action=action)
            r["retained_fraction"] = round(x.retained_fraction(c, artifact, valid[c["context_id"]]), 3) if fam == "F07" and isinstance(artifact, dict) else ""
            return r
        if j["stream"] == "patch_critic":
            outs = rec.get("paired_patch_paths", {}).get("outputs", {})
            for pn in ("interface_only", "evidence_guarded"):
                o = outs.get(pn, {}); act = o.get("action", {})
                rows.append(row("patch_critic/" + pn, o.get("accepted_artifact_assessment", {}), act.get("artifact"), act.get("path", "") + (":" + ",".join(act.get("reasons", [])) if act.get("reasons") else "")))
        else:
            rows.append(row(j["stream"], rec.get("final_assessment", {}), rec.get("final_artifact")))
    if plan["context_set"] == "nhanes":      # fixed name-prefix reviser, one row per input
        seen = set()
        for j in jobs.values():
            if j["proposal_id"] in seen: continue
            seen.add(j["proposal_id"]); c = j["context"]; p = x.prefix_reviser(c, j["initial_proposal"]); ass = x.evaluate_ext(c, p)
            rows.append({"unit": j["proposal_id"] + "__prefix__NA", "proposal_id": j["proposal_id"], "context_id": c["context_id"], "rule_id": c["rule_id"], "family": c["family"],
                         "archetype": c["archetype"], "seed": "NA", "initial": x.evaluate_ext(c, j["initial_proposal"])["verdict"], "status": "completed", "path": "prefix_rule_reviser",
                         "final": ass["verdict"], "pipeline": ass["pipeline"], "action": "", "retained_fraction": round(x.retained_fraction(c, p, valid[c["context_id"]]), 3)})
    a.out_dir.mkdir(parents=True, exist_ok=False)
    with (a.out_dir / "outcomes.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def tally(rs):
        rep = [r for r in rs if r["initial"] == v4.F]; pre = [r for r in rs if r["initial"] == v4.T]
        rf = [float(r["retained_fraction"]) for r in rs if r["retained_fraction"] != ""]
        return {"repair": [sum(r["final"] == v4.T for r in rep), len(rep)], "preserve": [sum(r["final"] == v4.T for r in pre), len(pre)],
                "harmful": sum(r["final"] == v4.F for r in pre), "supported": [sum(r["final"] == v4.T for r in rs), len(rs)],
                "no_output": sum(r["pipeline"] in ("not_evaluated", "schema_failure") for r in rs), "mean_retained_fraction": round(statistics.mean(rf), 3) if rf else None}
    summary = {"arm": plan["arm"], "context_set": plan["context_set"], "thinking": plan["thinking"], "model": plan["model"], "seeds": plan["seeds"],
               "by_path": {p: tally([r for r in rows if r["path"] == p]) for p in PATHS + ["prefix_rule_reviser"] if any(r["path"] == p for r in rows)}, "by_family_path": {}, "by_archetype_path": {}}
    for fam in sorted({r["family"] for r in rows}):
        for p in PATHS + ["prefix_rule_reviser"]:
            rs = [r for r in rows if r["family"] == fam and r["path"] == p]
            if rs: summary["by_family_path"][fam + "|" + p] = tally(rs)
    if plan["context_set"] == "nhanes":
        for r0 in sorted({(r["archetype"]) for r in rows}):
            for p in PATHS + ["prefix_rule_reviser"]:
                rs = [r for r in rows if r["archetype"] == r0 and r["path"] == p]
                if rs: summary["by_archetype_path"][r0 + "|" + p] = tally(rs)
    summary["unit_status"] = dict(collections.Counter(r["status"] for r in rows if r["path"] in ("self_review", "patch_critic/interface_only")))
    ev = [json.loads(s) for s in (a.run_dir / "requests.jsonl").read_text().splitlines() if s.strip()]
    st = collections.defaultdict(lambda: {"n": 0, "finish": collections.Counter(), "completion_tokens": [], "prompt_tokens": 0, "seconds": 0.0, "reasoning_field": 0, "think_tag": 0, "errors": 0})
    for e in ev:
        s = st[e["stage"]]; s["n"] += 1; s["seconds"] += e.get("elapsed_seconds", 0)
        if e.get("status") != "completed": s["errors"] += 1; continue
        msg = e["response"]["choices"][0]["message"]; s["finish"][e["response"]["choices"][0]["finish_reason"]] += 1
        s["completion_tokens"].append(e["response"]["usage"]["completion_tokens"]); s["prompt_tokens"] += e["response"]["usage"]["prompt_tokens"]
        if msg.get("reasoning_content") or msg.get("reasoning"): s["reasoning_field"] += 1
        if "<think>" in (msg.get("content") or "") or "</think>" in (msg.get("content") or ""): s["think_tag"] += 1
    summary["requests"] = {k: {"n": v["n"], "errors": v["errors"], "finish_reasons": dict(v["finish"]), "median_completion_tokens": statistics.median(v["completion_tokens"]) if v["completion_tokens"] else None,
                              "prompt_tokens": v["prompt_tokens"], "summed_client_seconds": round(v["seconds"], 1), "responses_with_reasoning_field": v["reasoning_field"],
                              "responses_with_think_tags": v["think_tag"]} for k, v in st.items()}
    try: summary["run_report"] = json.loads((a.run_dir / "run_report.json").read_text())
    except Exception: summary["run_report"] = None
    try: summary["server_model_entry"] = json.loads((a.run_dir / "models.json").read_text())["data"][0]
    except Exception: summary["server_model_entry"] = None
    try: summary["server_version"] = json.loads((a.run_dir / "server_version.json").read_text())
    except Exception: summary["server_version"] = None
    (a.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"arm": summary["arm"], "by_path": summary["by_path"], "requests": {k: {kk: vv for kk, vv in v.items() if kk in ("n", "errors", "finish_reasons", "responses_with_reasoning_field", "responses_with_think_tags")} for k, v in summary["requests"].items()}}, indent=1))


if __name__ == "__main__":
    main()
