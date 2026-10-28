"""Offline replay of the archived runs. No network or model calls; standard library only."""

import ast, copy, csv, hashlib, json
from pathlib import Path


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def canon(x):
    return sha_bytes(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, x):
    path.write_text(json.dumps(x, indent=2) + "\n", encoding="utf-8")


def pure_functions(source, names, env):
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
    for n in nodes:
        if n.decorator_list or any(isinstance(x, (ast.Import, ast.ImportFrom)) for x in ast.walk(n)):
            raise ValueError("Unsafe scorer structure")
        if any(
            isinstance(x, ast.Name)
            and x.id in {"open", "eval", "exec", "compile", "__import__", "os", "urllib", "subprocess", "Path"}
            for x in ast.walk(n)
        ):
            raise ValueError("Unsafe scorer name")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "restricted_authored_scoring", "exec"), env)
    return env


def principal(base, out):
    d = base / "experiments/core_contexts"
    plan = load(d / "plan.json")
    jobs = load(d / "jobs.json")
    events = load(d / "request_ledger.json")
    units = load(d / "units.json")
    refs = load(d / "references.json")
    source = (d / "p6_integrated_development_v0_4.py").read_text()
    assert canon(plan) == "0e8f19089e1c30abd239e31980645f17a566369e37422b58228389a7f5d74250"
    assert (
        sha_bytes((d / "p6_integrated_development_v0_4.py").read_bytes()) == plan["script_sha256"]
        and canon(jobs) == plan["jobs_sha256"]
    )
    assert len(jobs) == len(units) == 192 and len(refs) == 48
    assert sorted(e["request_index"] for e in events) == list(range(1, 385))
    assert all(
        not e["omitted_request_field_names"] and canon(e["request"]) == e["original_request_sha256"] for e in events
    )
    eidx = {(e["unit"], e["stage"]): e for e in events}
    assert len(eidx) == 384
    ns = pure_functions(
        source,
        {"sha", "same", "schema_errors", "facts", "evaluate", "guard_support", "apply", "assess_paths", "prompts"},
        {
            "json": json,
            "copy": copy,
            "hashlib": hashlib,
            "T": "supported",
            "F": "contradicted_contract",
            "U": "insufficient_evidence",
        },
    )
    refmap = {r["proposal_id"]: r for r in refs}
    outputs = []
    usage = []
    for j in jobs:
        unit = j["unit"]
        c, p = j["context"], j["initial_proposal"]
        review = eidx[unit, "review"]
        revision = eidx[unit, "revision"]
        msgs, task, instruction = ns["prompts"](c, p, j["stream"])
        assert (msgs, task, instruction) == (j["review_messages"], j["revision_task"], j["revision_instruction"])
        review_text = review["response"]["choices"][0]["message"]["content"]
        final_msgs = [
            {"role": "system", "content": "Use only the task evidence. Review advice cannot override the contract."},
            {"role": "user", "content": json.dumps(task) + "\nREVIEW:\n" + review_text + "\n" + instruction},
        ]
        for e, m, seed in ((review, msgs, 42), (revision, final_msgs, 1042)):
            assert e["request"] == {
                "model": plan["model"],
                "messages": m,
                "temperature": plan["temperature"],
                "max_tokens": plan["max_tokens"],
                "seed": seed,
            }
            u = e["response"]["usage"]
            assert u["total_tokens"] == u["prompt_tokens"] + u["completion_tokens"]
            usage.append(
                {
                    "unit": unit,
                    "stream": j["stream"],
                    "stage": e["stage"],
                    "prompt_tokens": u["prompt_tokens"],
                    "completion_tokens": u["completion_tokens"],
                    "total_tokens": u["total_tokens"],
                    "client_seconds": e["elapsed_seconds"],
                    "finish_reason": e["response"]["choices"][0]["finish_reason"],
                }
            )
        initial = ns["evaluate"](c, p)
        assert initial == refmap[j["proposal_id"]]["assessment"]
        rec = {"unit": unit, "stream": j["stream"], "status": "started", "initial_assessment": initial}
        text = revision["response"]["choices"][0]["message"]["content"]
        try:
            obj = json.loads(text)
        except (ValueError, TypeError):
            rec.update(status="unparseable_output", raw_final=text)
        else:
            if j["stream"] == "patch_critic":
                rec["paired_patch_paths"] = ns["assess_paths"](c, p, obj)
            else:
                rec["final_artifact"] = obj
                rec["final_assessment"] = ns["evaluate"](c, obj)
            rec["status"] = "completed"
        assert rec == units[unit], unit
        for path in (["interface_only", "evidence_guarded"] if j["stream"] == "patch_critic" else [j["stream"]]):
            a = (
                rec.get("paired_patch_paths", {})
                .get("outputs", {})
                .get(path, {})
                .get("accepted_artifact_assessment", {})
                if j["stream"] == "patch_critic"
                else rec.get("final_assessment", {})
            )
            outputs.append(
                {
                    "unit": unit,
                    "path": "patch_critic/" + path if j["stream"] == "patch_critic" else path,
                    "initial": initial["verdict"],
                    "final": a.get("verdict", "not_evaluated"),
                    "pipeline": a.get("pipeline", "not_evaluated"),
                }
            )
    for name, rows in [("principal_outcomes.csv", outputs), ("principal_requests.csv", usage)]:
        with (out / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    from rule_reference import propose

    contexts = {j["context"]["context_id"]: j["context"] for j in jobs}
    baseline = []
    for cid, c in sorted(contexts.items()):
        p = propose(copy.deepcopy(c))
        baseline.append({"context_id": cid, "proposal": p, "assessment": ns["evaluate"](c, p)})
    assert len(baseline) == 24 and all(r["assessment"]["verdict"] == "supported" for r in baseline)
    write(out / "posthoc_rule_reference.json", baseline)
    return {
        "exact_units": 192,
        "references": 48,
        "requests": 384,
        "prompt_tokens": sum(r["prompt_tokens"] for r in usage),
        "completion_tokens": sum(r["completion_tokens"] for r in usage),
        "total_tokens": sum(r["total_tokens"] for r in usage),
        "summed_client_seconds": sum(r["client_seconds"] for r in usage),
        "review_limit_stops": sum(r["stage"] == "review" and r["finish_reason"] == "length" for r in usage),
        "posthoc_supported_contexts": 24,
        "new_model_calls": 0,
    }


def pilot(base, out):
    archive = base / "experiments/preliminary_study"
    run = archive / "outputs/agent_comparison/20261025T064454685602Z"
    provenance = load(run / "provenance.json")
    source = (archive / "scripts/run_depression_agent_comparison_v1.py").read_text()
    assert (
        sha_bytes((archive / "scripts/run_depression_agent_comparison_v1.py").read_bytes())
        == provenance["script_sha256"]
    )
    constants = {"VERSION", "FIELDS", "LIST_FIELDS", "PENDING", "CANDIDATES", "CASES"}
    nodes = [
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)
    ]
    ns = {"json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "literal_pilot_definitions", "exec"), ns)
    pure_functions(source, {"parse_proposal", "structure_findings", "score"}, ns)
    cases = {c["id"]: c for c in ns["CASES"]}
    events = [json.loads(s) for s in (run / "requests.jsonl").read_text().splitlines() if s.strip()]
    idx = {(e["unit"], e["stage"]): e for e in events}
    records = [load(p) for p in sorted(run.glob("*__*.json"))]
    assert len(records) == 45 and len(events) == len(idx) == 135
    summary = {}
    details = []
    drafts = {}
    for r in records:
        condition = r["condition"]
        s = summary.setdefault(
            condition,
            {
                "units": 0,
                "strict_final_pass": 0,
                "normalized_final_pass": 0,
                "normalized_improvements": 0,
                "normalized_regressions": 0,
            },
        )
        s["units"] += 1
        per = {}
        for stage in ("initial", "final"):
            text = idx[r["unit"], stage]["response"]["choices"][0]["message"]["content"]
            strict = ns["score"](text, cases[r["case"]])
            assert strict == r[stage], r["unit"]
            candidate = ns["parse_proposal"](text)
            normalized = copy.deepcopy(candidate)
            changed = False
            if (
                isinstance(normalized, dict)
                and isinstance(normalized.get("claims"), str)
                and normalized["claims"] in {"no_empirical_claim", "internal_development_design_only"}
            ):
                normalized["claims"] = [normalized["claims"]]
                changed = True
            norm = ns["score"](json.dumps(normalized), cases[r["case"]]) if changed else strict
            per[stage] = {"strict": strict, "normalized": norm, "normalization_applied": changed}
            if stage == "initial":
                drafts.setdefault((r["case"], r["seed"]), []).append(text)
        s["strict_final_pass"] += int(per["final"]["strict"]["contract_pass"])
        s["normalized_final_pass"] += int(per["final"]["normalized"]["contract_pass"])
        s["normalized_improvements"] += int(
            not per["initial"]["normalized"]["contract_pass"] and per["final"]["normalized"]["contract_pass"]
        )
        s["normalized_regressions"] += int(
            per["initial"]["normalized"]["contract_pass"] and not per["final"]["normalized"]["contract_pass"]
        )
        details.append({"unit": r["unit"], **per})
    old = load(run / "posthoc_claims_sensitivity_20261026T162339932791Z/run_report.json")
    for row in old["aggregate"]:
        s = summary[row["condition"]]
        assert (
            s["strict_final_pass"] == row["final_strict_pass"]
            and s["normalized_final_pass"] == row["final_normalized_pass"]
            and s["normalized_improvements"] == row["normalized_revision_improvements"]
            and s["normalized_regressions"] == row["normalized_revision_regressions"]
        )
    assert len(drafts) == 15 and all(len(x) == 3 and len(set(x)) == 1 for x in drafts.values())
    write(out / "pilot_replayed_scores.json", details)
    return {
        "exact_units": 45,
        "requests": 135,
        "strict_and_posthoc_scores_reproduced": True,
        "matched_identical_initial_groups": 15,
        "conditions": summary,
        "new_model_calls": 0,
        "normalization": "Post hoc; strict results remain primary.",
    }


def reference_metadata(base, out):
    archive = base / "experiments/preliminary_study"
    run = archive / "outputs/reference_evaluation/depression_20261025T063110357273Z"
    r = load(run / "run_report.json")
    assert sha_bytes((archive / "configs/nhanes_depression_dev_v7.json").read_bytes()) == r["config_sha256"]
    assert sha_bytes((archive / "scripts/run_depression_reference_v1.py").read_bytes()) == r["runner_sha256"]
    for p, h in r["source_sha256"].items():
        assert sha_bytes((archive / p).read_bytes()) == h, p
    assert r["cohort"]["complete_outcome"] == 5068 and r["cohort"]["positive"] == 459 and len(r["metrics"]) == 6
    with (out / "recorded_reference_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(r["metrics"][0]))
        w.writeheader()
        w.writerows(r["metrics"])
    return {
        "recorded_report_verified": True,
        "numerical_refit_performed": False,
        "cohort": r["cohort"],
        "warning": "Metrics are exported from the checked archived report; fresh numerical reproduction requires the public XPT inputs and optional reference adapter.",
    }
