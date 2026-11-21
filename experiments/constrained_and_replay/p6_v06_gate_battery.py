"""P6 gate operating-characteristic battery (offline, deterministic, no model calls, no network).

For every initial input of every context (core24 and NHANES-label sets), enumerate every single-field edit
(boolean flip; list element added or removed; list cleared; string replaced by each value the same field takes in
the context family), wrap it as a patch, and pass it through both application paths of the verified v0.4 runner:
the interface-only path and the evidence-guarded path. The evaluator verdict on the edited artifact is the reference.
Patches are issued under four evidence-citation conditions: applicable IDs, no IDs, IDs of another scope, and
nonexistent IDs.

Reports (i) agreement between the evidence-gate support check and the evaluator on the edited artifacts, and
(ii) acceptance of harmful, neutral and repairing edits by each path.

Usage: python p6_v06_gate_battery.py --out-dir NEW_DIR
"""
import argparse, collections, copy, csv, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p6_extended_v0_5 as x

v4 = x.v4
T, F, U = v4.T, v4.F, v4.U
ATTACKS = ("applicable_ids", "no_ids", "foreign_scope_ids", "nonexistent_ids")


def universe(c, field, value):
    f = v4.facts(c)
    if c["family"] in ("F01", "F02"):
        return sorted(f["features"])
    if c["family"] == "F07":
        return sorted(f["candidates"])
    if c["family"] == "F03" and "records" in f:
        return sorted(f["records"])
    return []


def field_values(bank):
    vals = collections.defaultdict(set)
    for it in bank:
        fam = it["public"]["family"]
        for role in ("valid_or_conservative", "counterpart"):
            for k, v in it[role].items():
                if isinstance(v, str):
                    vals[(fam, k)].add(v)
    return vals


def mutations(c, p, strvals):
    for k, v in p.items():
        if isinstance(v, bool):
            yield k, "flip", {**p, k: (not v)}
        elif isinstance(v, list):
            for e in v:
                yield k, "remove:" + e, {**p, k: [z for z in v if z != e]}
            for e in universe(c, k, v):
                if e not in v:
                    yield k, "add:" + e, {**p, k: v + [e]}
            if v:
                yield k, "clear", {**p, k: []}
        elif isinstance(v, str):
            for alt in sorted(strvals.get((c["family"], k), ())):
                if alt != v:
                    yield k, "set:" + alt, {**p, k: alt}


def with_ids(c, patch, mode):
    q = copy.deepcopy(patch)
    scoped = [r["evidence_id"] for r in c["evidence"] if r["scope_id"] == c["scope_id"]]
    foreign = [r["evidence_id"] for r in c["evidence"] if r["scope_id"] != c["scope_id"]]
    for op in q["operations"]:
        op["evidence_ids"] = {"applicable_ids": scoped, "no_ids": [], "foreign_scope_ids": foreign, "nonexistent_ids": ["FAKE/E99"]}[mode]
    return q


def klass(start, end):
    if start == T and end != T:
        return "harmful"
    if start == T and end == T:
        return "neutral_supported"
    if start != T and end == T:
        return "repair"
    return "neutral_unsupported"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out-dir", type=Path, required=True); a = ap.parse_args()
    rows, cand = [], []
    for setname in ("core24", "nhanes"):
        bank = x.context_items(setname); strvals = field_values(bank)
        for it in bank:
            c = it["public"]
            for role in ("valid_or_conservative", "counterpart"):
                p = it[role]; start = x.evaluate_ext(c, p)["verdict"]
                cand.append({"set": setname, "context_id": c["context_id"], "family": c["family"], "archetype": c["archetype"], "role": role,
                             "edit": "(input)", "truth": start, "gate_support": x.guard_ext(c, p)})
                for field, desc, t in mutations(c, p, strvals):
                    truth = x.evaluate_ext(c, t)["verdict"]
                    cand.append({"set": setname, "context_id": c["context_id"], "family": c["family"], "archetype": c["archetype"], "role": role,
                                 "edit": field + ":" + desc, "truth": truth, "gate_support": x.guard_ext(c, t)})
                    base = v4.patch(c, p, t)
                    if not base["operations"]:
                        continue
                    for mode in ATTACKS:
                        res = v4.assess_paths(c, p, with_ids(c, base, mode))
                        A, B = res["outputs"]["interface_only"]["action"], res["outputs"]["evidence_guarded"]["action"]
                        rows.append({"set": setname, "context_id": c["context_id"], "family": c["family"], "archetype": c["archetype"], "role": role,
                                     "edit": field + ":" + desc, "ids": mode, "start": start, "truth_after": truth, "class": klass(start, truth),
                                     "A_accepts": int(A["accepted"]), "B_accepts": int(B["accepted"]),
                                     "A_final": res["outputs"]["interface_only"]["accepted_artifact_assessment"]["verdict"],
                                     "B_final": res["outputs"]["evidence_guarded"]["accepted_artifact_assessment"]["verdict"],
                                     "B_reason": ";".join(B["reasons"])})
    a.out_dir.mkdir(parents=True, exist_ok=False)
    for name, data in (("edits.csv", rows), ("candidates.csv", cand)):
        with (a.out_dir / name).open("w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)

    S = {"edits": len(rows) // len(ATTACKS), "candidate_artifacts": len(cand), "agreement": {}, "by_ids_and_class": {}, "gate_disagreements": []}
    for grp in ("core24", "nhanes"):
        cs = [r for r in cand if r["set"] == grp]
        S["agreement"][grp] = {"n": len(cs), "agree": sum(r["truth"] == r["gate_support"] for r in cs),
                               "gate_T_truth_not_T": sum(r["gate_support"] == T and r["truth"] != T for r in cs),
                               "gate_not_T_truth_T": sum(r["gate_support"] != T and r["truth"] == T for r in cs)}
    for fam in sorted({r["family"] for r in cand}):
        cs = [r for r in cand if r["family"] == fam]
        S["agreement"][fam] = {"n": len(cs), "agree": sum(r["truth"] == r["gate_support"] for r in cs),
                               "gate_T_truth_not_T": sum(r["gate_support"] == T and r["truth"] != T for r in cs),
                               "gate_not_T_truth_T": sum(r["gate_support"] != T and r["truth"] == T for r in cs)}
    for mode in ATTACKS:
        for k in ("harmful", "neutral_supported", "repair", "neutral_unsupported"):
            rs = [r for r in rows if r["ids"] == mode and r["class"] == k]
            S["by_ids_and_class"][mode + "|" + k] = {"n": len(rs), "interface_accepts": sum(r["A_accepts"] for r in rs), "evidence_gate_accepts": sum(r["B_accepts"] for r in rs),
                                                  "interface_accepted_and_final_not_supported": sum(1 for r in rs if r["A_accepts"] and r["A_final"] != T),
                                                  "gate_accepted_and_final_not_supported": sum(1 for r in rs if r["B_accepts"] and r["B_final"] != T)}
    for r in cand:
        if r["family"] == "F07" and r["gate_support"] != r["truth"]:
            S["gate_disagreements"].append({k: r[k] for k in ("context_id", "archetype", "role", "edit", "truth", "gate_support")})
    S["note"] = "F01-F06: the gate support check and the evaluator implement the same rule semantics (agreement is by construction); F07: gate uses repository name-prefix rules, evaluator uses author reference sets."
    (a.out_dir / "summary.json").write_text(json.dumps(S, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: S[k] for k in ("edits", "candidate_artifacts", "agreement")}, indent=2))
    for k, v in S["by_ids_and_class"].items():
        print(f"{k:40s} {v}")
    print("F07 gate/evaluator disagreements:", len(S["gate_disagreements"]))


if __name__ == "__main__":
    main()
