"""P6 v0.5 extended synthetic development runner (standard library only).

Adds to the verified v0.4 runner (imported unchanged, hash-checked):
  * an NHANES-label context set (family F07, 17 contexts) whose candidate variables carry real
    2015-2016 codebook labels; the evaluator uses author reference sets, the evidence gate uses the
    repository's name-prefix rules;
  * a switch for the Qwen3 thinking mode (server default or off);
  * several seeds per input, and concurrent requests;
  * a fixed name-prefix rule baseline that can be scored offline.
Generation needs an exact plan hash, never retries, never resumes, and never sends author-only data.
"""
import argparse, copy, hashlib, json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p6_integrated_development_v0_4 as v4

T, F, U = v4.T, v4.F, v4.U
STREAMS = v4.STREAMS
VERSION = "p6_extended_0.5"
V4_SHA256 = "1649d94540600146e4f562c48525b68f82813b2fa6e360c8fa881bbdb8b7cb83"
sha = v4.sha

# ----------------------------------------------------------------------------------------------
# Real NHANES 2015-2016 codebook labels (wwwn.cdc.gov, retrieved 27 October 2026) and component names
# ----------------------------------------------------------------------------------------------
COMP = {"BIOPRO": "Standard Biochemistry Profile", "GHB": "Glycohemoglobin", "GLU": "Plasma Fasting Glucose",
        "OGTT": "Oral Glucose Tolerance Test", "ALB_CR": "Albumin & Creatinine - Urine", "BPX": "Blood Pressure",
        "BPQ": "Blood Pressure & Cholesterol", "DIQ": "Diabetes", "DPQ": "Mental Health - Depression Screener",
        "RXQ_RX": "Prescription Medications"}
LAB = {
    "LBXSAL": ("BIOPRO", "Albumin, refrigerated serum (g/dL)"), "LBXSAPSI": ("BIOPRO", "Alkaline Phosphatase (ALP) (IU/L)"),
    "LBXSASSI": ("BIOPRO", "Aspartate Aminotransferase (AST) (U/L)"), "LBXSATSI": ("BIOPRO", "Alanine Aminotransferase (ALT) (U/L)"),
    "LBXSCA": ("BIOPRO", "Total Calcium (mg/dL)"), "LBXSCH": ("BIOPRO", "Cholesterol, refrigerated serum (mg/dL)"),
    "LBXSCR": ("BIOPRO", "Creatinine, refrigerated serum (mg/dL)"), "LBDSCRSI": ("BIOPRO", "Creatinine, refrigerated serum (umol/L)"),
    "LBXSGL": ("BIOPRO", "Glucose, refrigerated serum (mg/dL)"), "LBDSGLSI": ("BIOPRO", "Glucose, refrigerated serum (mmol/L)"),
    "LBXSGTSI": ("BIOPRO", "Gamma Glutamyl Transferase (GGT) (U/L)"), "LBXSIR": ("BIOPRO", "Iron, refrigerated serum (ug/dL)"),
    "LBXSKSI": ("BIOPRO", "Potassium (mmol/L)"), "LBXSLDSI": ("BIOPRO", "Lactate Dehydrogenase (LDH) (U/L)"),
    "LBXSNASI": ("BIOPRO", "Sodium (mmol/L)"), "LBXSTB": ("BIOPRO", "Total Bilirubin (mg/dL)"),
    "LBXSTP": ("BIOPRO", "Total Protein (g/dL)"), "LBXSTR": ("BIOPRO", "Triglycerides, refrig serum (mg/dL)"),
    "LBXSUA": ("BIOPRO", "Uric acid (mg/dL)"),
    "LBXGH": ("GHB", "Glycohemoglobin (%)"), "LBXGLU": ("GLU", "Fasting Glucose (mg/dL)"),
    "BPXSY1": ("BPX", "Systolic: Blood pres (1st rdg) mm Hg"), "BPXDI1": ("BPX", "Diastolic: Blood pres (1st rdg) mm Hg"),
    "BPXSY2": ("BPX", "Systolic: Blood pres (2nd rdg) mm Hg"), "BPXDI2": ("BPX", "Diastolic: Blood pres (2nd rdg) mm Hg"),
    "BPXPLS": ("BPX", "60 sec. pulse (30 sec. pulse * 2)"), "BPACSZ": ("BPX", "Coded cuff size"),
    "BPQ020": ("BPQ", "Ever told you had high blood pressure"), "BPQ040A": ("BPQ", "Taking prescription for hypertension"),
    "BPD035": ("BPQ", "Age told had hypertension"), "BPQ080": ("BPQ", "Doctor told you - high cholesterol level"),
    "DID040": ("DIQ", "Age when first told you had diabetes"), "DID060": ("DIQ", "How long taking insulin"),
    "DIQ070": ("DIQ", "Take diabetic pills to lower blood sugar"), "DIQ300S": ("DIQ", "What was your recent SBP"),
    "DIQ300D": ("DIQ", "What was your recent DBP"),
    "DPQ020": ("DPQ", "Feeling down, depressed, or hopeless"), "DPQ040": ("DPQ", "Feeling tired or having little energy"),
    "DPQ100": ("DPQ", "Difficulty these problems have caused"),
    "URXUMA": ("ALB_CR", "Albumin, urine (ug/mL)"), "URXUMS": ("ALB_CR", "Albumin, urine (mg/L)"),
    "URDUMALC": ("ALB_CR", "Albumin, urine comment code"), "URXCRS": ("ALB_CR", "Creatinine, urine (umol/L)"),
    "URDACT": ("ALB_CR", "Albumin creatinine ratio (mg/g)"),
    "RXDDRUG": ("RXQ_RX", "Generic drug name"), "RXDDRGID": ("RXQ_RX", "Generic drug code"),
    "RXDRSC1": ("RXQ_RX", "ICD-10-CM code 1"), "RXDRSD1": ("RXQ_RX", "ICD-10-CM code 1 description"),
}
RX = {"RXDDRUG", "RXDDRGID", "RXDRSC1", "RXDRSC2", "RXDRSC3", "RXDRSD1", "RXDRSD2", "RXDRSD3"}
# Author reference: variables that may not be selected, by task (criteria A defining, B restatement, C diagnosis/treatment)
FORBID = {
    "diabetes": {"LBXGH", "LBXGLU", "LBDGLUSI", "LBXGLT", "LBDGLTSI", "GTDCODE", "LBXSGL", "LBDSGLSI", "DID040", "DIQ050", "DID060", "DIQ060U", "DIQ070", "DIQ080"} | RX,
    "hypertension": {f"BPXSY{i}" for i in range(1, 5)} | {f"BPXDI{i}" for i in range(1, 5)} | {"DIQ300S", "DIQ300D", "BPQ020", "BPQ030", "BPD035", "BPQ040A", "BPQ050A"} | RX,
    "depression": {f"DPQ0{i}0" for i in range(1, 10)} | {"DPQ100"} | RX,
    "ckd": {"LBXSCR", "URXUMA", "URXUCR", "URDACT", "LBDSCRSI", "URXUMS", "URXCRS", "URDUMALC", "URDUCRLC"} | RX,
}
# Repository name-prefix rules (Dr-PKDP/P6-Population-Valid-Agentic-Clinical-Prediction, src/lineage_validator.py, commit 7876bf0)
PREFIX = {"diabetes": r"^(LBXGH|LBDGH|LBXGLU|LBDGLU|LBXIN|LBDIN|DIQ)", "hypertension": r"^(BPX|BPQ)",
          "depression": r"^(DPQ|FNQ)", "ckd": r"^(LBXSCR|LBDCRE|URXUMA|URXUCR|URDACT|URXUACR|KIQ|CKQ)"}
DESIGN = r"^(SDMVSTRA|SDMVPSU|WTMEC|WTINT)"
OUTCOME = {
    "diabetes": "Diabetes (screening). Cases are identified from glycohemoglobin, fasting or two-hour oral glucose tolerance test glucose, or self-reported diagnosis or glucose-lowering treatment.",
    "hypertension": "Hypertension (screening). Cases are identified from measured blood pressure readings, or self-reported diagnosis or antihypertensive treatment.",
    "depression": "Elevated depressive symptoms (screening), defined from the PHQ-9 questionnaire (Depression Screener component).",
    "ckd": "Chronic kidney disease (screening), defined from serum creatinine (estimated glomerular filtration rate) and the urine albumin-to-creatinine ratio.",
}
RULE = ("Select predictors for the stated outcome using each candidate's label and component. A variable may not be selected if it "
        "(a) is part of the outcome definition or its measurement instrument; (b) records the same quantity as such a variable in other units, "
        "as a comment or detection code, or in another component; or (c) records a diagnosis of the condition, treatment for it, or the reason "
        "for taking a medication. Variables that identify the prescription medications a person takes, or the reason for use, count as recording "
        "treatment. Variable names alone do not decide; a variable unrelated to the outcome definition may be selected, including one whose name "
        "resembles an excluded variable. An empty selection may express deferral.")

# (task, archetype, valid selection, forbidden variables added in the counterpart, extra unselected candidates)
SPECS = [
    ("diabetes", "defining_measure", ["LBXSCH", "LBXSTR", "LBXSATSI", "BPXSY1"], ["LBXGH"], ["LBXGLU", "LBXSGTSI", "LBXSUA", "LBXSKSI"]),
    ("diabetes", "other_component_glucose", ["LBXSCH", "LBXSTR", "LBXSGTSI", "LBXSUA"], ["LBDSGLSI"], ["LBXGH", "LBXSATSI", "BPXSY1", "LBXSNASI"]),
    ("diabetes", "treatment_records", ["LBXSCH", "LBXSTR", "BPXSY1", "LBXSATSI"], ["RXDDRUG", "RXDRSC1"], ["RXDDRGID", "RXDRSD1", "LBXGH", "LBXSUA"]),
    ("diabetes", "naming_exception", ["LBXSCH", "LBXSTR", "LBXSGTSI", "BPXPLS"], ["DID040"], ["DIQ070", "LBXGH", "LBXSATSI", "LBXSUA"]),
    ("hypertension", "defining_measure", ["LBXSGL", "LBXSCH", "LBXSTR", "LBXSUA"], ["BPXSY2"], ["BPXDI1", "LBXSNASI", "LBXSKSI", "LBXSATSI"]),
    ("hypertension", "cross_component_bp", ["LBXSGL", "LBXSCH", "LBXSTR", "LBXSKSI"], ["DIQ300S"], ["DIQ300D", "BPXSY1", "LBXSUA", "LBXSNASI"]),
    ("hypertension", "treatment_records", ["LBXSGL", "LBXSCH", "LBXSUA", "LBXSNASI"], ["RXDDRUG", "RXDRSD1"], ["RXDDRGID", "RXDRSC1", "BPQ040A", "LBXSTR"]),
    ("hypertension", "naming_exception", ["LBXSGL", "LBXSCH", "LBXSTR", "LBXSUA"], ["BPD035"], ["BPQ020", "BPXSY1", "LBXSKSI", "LBXSATSI"]),
    ("hypertension", "prefix_lookalike_control", ["LBXSGL", "LBXSCH", "BPXPLS", "BPQ080"], ["BPXDI2"], ["BPXSY1", "LBXSTR", "LBXSUA", "BPACSZ"]),
    ("depression", "defining_item", ["LBXSGL", "LBXSCH", "BPXSY1", "LBXSATSI"], ["DPQ040"], ["DPQ020", "LBXSTP", "LBXSTR", "LBXSIR"]),
    ("depression", "instrument_item_10", ["LBXSGL", "LBXSCH", "BPXSY1", "LBXSTR"], ["DPQ100"], ["DPQ020", "LBXSATSI", "LBXSIR", "LBXSCA"]),
    ("depression", "treatment_drug", ["LBXSGL", "LBXSCH", "LBXSTP", "LBXSATSI"], ["RXDDRUG", "RXDDRGID"], ["RXDRSC1", "BPXSY1", "LBXSIR", "LBXSTR"]),
    ("depression", "treatment_indication", ["LBXSGL", "LBXSCH", "BPXSY1", "LBXSTB"], ["RXDRSC1", "RXDRSD1"], ["RXDDRUG", "LBXSATSI", "LBXSTR", "LBXSCA"]),
    ("ckd", "defining_measure", ["LBXSGL", "LBXSCH", "LBXSAL", "BPXSY1"], ["LBXSCR"], ["URDACT", "LBXSATSI", "LBXSTR", "LBXSIR"]),
    ("ckd", "unit_restatement", ["LBXSGL", "LBXSCH", "LBXSAL", "LBXSATSI"], ["LBDSCRSI"], ["LBXSCR", "URXUMA", "BPXSY1", "LBXSTR"]),
    ("ckd", "urine_restatement_comment", ["LBXSGL", "LBXSCH", "LBXSAL", "BPXSY1"], ["URXUMS", "URDUMALC"], ["URXUMA", "URXCRS", "LBXSATSI", "LBXSTR"]),
    ("ckd", "treatment_records", ["LBXSGL", "LBXSCH", "LBXSAL", "LBXSATSI"], ["RXDDRUG", "RXDRSC1"], ["RXDDRGID", "RXDRSD1", "LBXSCR", "BPXSY1"]),
]


def nhanes_items():
    bank = []
    for n, (task, arch, valid, add, extra) in enumerate(SPECS, 1):
        cid = f"P6D05_N{n:03d}"
        cand = sorted(set(valid) | set(add) | set(extra), key=lambda v: (LAB[v][0], v))
        facts = {"task_id": task, "outcome": OUTCOME[task],
                 "candidates": {v: {"component": LAB[v][0], "component_name": COMP[LAB[v][0]], "label": LAB[v][1]} for v in cand}}
        public = {"context_id": cid, "family": "F07", "archetype": arch, "scope_id": cid, "cutoff": 10,
                  "evidence": [{"evidence_id": cid + "/E01", "scope_id": cid, "content": facts},
                               {"evidence_id": "OTHER/" + cid + "/E02", "scope_id": "OTHER", "content": {"note": "This is evidence for another scope."}}],
                  "rule_id": "F07/" + arch, "public_rule": RULE,
                  "proposal_schema": {"selected": {"type": "string_list", "allow_empty": True}},
                  "source_status": "SYNTHETIC_FROM_PUBLIC_CODEBOOK_LABELS_DEVELOPMENT_NOT_HELDOUT", "dependence_unit": "UNRESOLVED_F07"}
        bank.append({"public": public, "valid_or_conservative": {"selected": list(valid)},
                     "counterpart": {"selected": list(valid) + list(add)}, "counterpart_expected": F})
    return bank


def context_items(name):
    if name == "core24":
        return v4.contexts()
    if name == "nhanes":
        return nhanes_items()
    raise SystemExit("unknown context set " + name)


# ----------------------------------------------------------------------------------------------
# Evaluator and evidence-gate support check for F07 (v4 functions are used unchanged for F01-F06)
# ----------------------------------------------------------------------------------------------
_eval4, _guard4 = v4.evaluate, v4.guard_support


def prefix_flag(task, var):
    return bool(re.match(PREFIX[task], var.upper()) or re.match(DESIGN, var.upper()))


def evaluate_ext(c, p):
    if c["family"] != "F07":
        return _eval4(c, p)
    errors = v4.schema_errors(c, p)
    if errors:
        return {"verdict": U, "pipeline": "schema_failure", "findings": errors, "trace": []}
    f = v4.facts(c)
    cand, bad = f["candidates"], FORBID[f["task_id"]]
    trace = [{"variable": v, "state": U if v not in cand else F if v in bad else T} for v in p["selected"]]
    states = [x["state"] for x in trace]
    verdict = F if F in states else U if U in states else T
    return {"verdict": verdict, "pipeline": "assessable" if verdict != U else "evidence_insufficient",
            "findings": [] if verdict == T else ["lineage"], "trace": trace, "rule_id": c["rule_id"],
            "independent_scientific_validity": "NOT_ESTABLISHED"}


def guard_ext(c, p):
    """Evidence-gate support check. F01-F06: v0.4 implementation. F07: repository name-prefix rules."""
    if c["family"] != "F07":
        return _guard4(c, p)
    if v4.schema_errors(c, p):
        return U
    f = v4.facts(c)
    if any(v not in f["candidates"] for v in p["selected"]):
        return U
    return F if any(prefix_flag(f["task_id"], v) for v in p["selected"]) else T


v4.evaluate, v4.guard_support = evaluate_ext, guard_ext   # v4.apply / v4.assess_paths resolve these names at call time


def prefix_reviser(c, p):
    """Fixed baseline: remove every selected variable that the repository name-prefix rules flag."""
    task = v4.facts(c)["task_id"]
    return {"selected": [v for v in p["selected"] if not prefix_flag(task, v)]}


def retained_fraction(c, final, valid):
    s = set(final.get("selected", [])) if isinstance(final, dict) else set()
    return len(s & set(valid["selected"])) / len(valid["selected"]) if valid["selected"] else 1.0


def initial_inputs(items):
    for item in items:
        c = item["public"]
        for role in ("valid_or_conservative", "counterpart"):
            p = item[role]
            yield c, p, "P" + sha({"context": c["context_id"], "role": role})[:12].upper(), role


# ----------------------------------------------------------------------------------------------
def check():
    out = []
    for item in nhanes_items():
        c, good, bad = item["public"], item["valid_or_conservative"], item["counterpart"]
        assert evaluate_ext(c, good)["verdict"] == T and evaluate_ext(c, bad)["verdict"] == F
        fix = v4.assess_paths(c, bad, v4.patch(c, bad, good))
        assert fix["outputs"]["interface_only"]["accepted_artifact_assessment"]["verdict"] == T
        harm = v4.assess_paths(c, good, v4.patch(c, good, bad))
        assert harm["outputs"]["interface_only"]["action"]["accepted"]
        pr = prefix_reviser(c, bad)
        out.append({"context_id": c["context_id"], "archetype": c["archetype"], "task": v4.facts(c)["task_id"],
                    "guard_accepts_correct_patch": fix["outputs"]["evidence_guarded"]["action"]["accepted"],
                    "guard_blocks_harmful_patch": not harm["outputs"]["evidence_guarded"]["action"]["accepted"],
                    "prefix_reviser_verdict_on_counterpart": evaluate_ext(c, pr)["verdict"],
                    "prefix_reviser_retained_fraction": retained_fraction(c, pr, good)})
    core_ok = v4.check()["status"]
    return {"status": "PASS_OFFLINE", "nhanes_contexts": len(out), "core24_check": core_ok, "model_calls": 0, "rows": out}


def prepare(a):
    items = context_items(a.context_set)
    seeds = [int(x) for x in a.seeds.split(",")]
    jobs = []
    for c, p, pid, role in initial_inputs(items):
        for stream in STREAMS:
            for seed in seeds:
                review, task, instruction = v4.prompts(c, p, stream)
                jobs.append({"unit": f"{pid}__{stream}__{seed}", "proposal_id": pid, "author_role": role, "context": c, "initial_proposal": p,
                             "stream": stream, "seed": seed, "review_messages": review, "revision_task": task, "revision_instruction": instruction})
    plan = {"version": VERSION, "scope": "DEVELOPMENT_ONLY_NOT_CONFIRMATORY", "arm": a.arm, "context_set": a.context_set,
            "thinking": a.thinking, "model": a.model, "base_url": a.base_url, "seeds": seeds, "temperature": 0.2, "max_tokens": a.revision_max_tokens, "review_max_tokens": a.review_max_tokens,
            "timeout_seconds": 300, "retries": 0, "workers": a.workers, "contexts": len(items), "inputs": len(items) * 2,
            "generator_streams": list(STREAMS), "workflow_units": len(jobs), "max_generation_calls": len(jobs) * 2,
            "patch_paths_share_generation": True, "jobs_sha256": sha(jobs),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "v4_script_sha256": hashlib.sha256(Path(v4.__file__).read_bytes()).hexdigest(), "execution_authorized": False}
    d = a.output_dir
    d.mkdir(parents=True, exist_ok=False)
    v4.write(d / "jobs.json", jobs); v4.write(d / "plan.json", plan)
    v4.write(d / "AUTHOR_ONLY_input_states.json", [{"proposal_id": pid, "context_id": c["context_id"], "author_role": role,
                                                    "author_evaluator_state": evaluate_ext(c, p)["verdict"]} for c, p, pid, role in initial_inputs(items)])
    print(json.dumps({"status": "PREPARED_NOT_EXECUTED", "arm": a.arm, "directory": str(d), "plan_sha256": sha(plan), "units": len(jobs),
                      "max_generation_calls": plan["max_generation_calls"], "model_calls_made": 0}, indent=2))


def run(a):
    plan = json.loads((a.plan_dir / "plan.json").read_text()); jobs = json.loads((a.plan_dir / "jobs.json").read_text())
    if a.approve_plan_hash != sha(plan): raise SystemExit("Approval hash differs from exact plan; no calls made.")
    if sha(jobs) != plan["jobs_sha256"]: raise SystemExit("Job manifest changed; no calls made.")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != plan["script_sha256"]: raise SystemExit("Runner changed; prepare a fresh plan.")
    v4_hash = hashlib.sha256(Path(v4.__file__).read_bytes()).hexdigest()
    if v4_hash != plan["v4_script_sha256"] or v4_hash != V4_SHA256: raise SystemExit("v0.4 runner differs from the verified file; no calls made.")
    if a.output_dir.exists(): raise SystemExit("Output exists; no overwrite or automatic resume.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})); key = os.environ.get("OPENAI_API_KEY", "")

    def request(route, payload=None, root=False):
        headers = {"Content-Type": "application/json"}
        if key: headers["Authorization"] = "Bearer " + key
        base = plan["base_url"][:-3] if root else plan["base_url"]
        req = urllib.request.Request(base + route, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        with opener.open(req, timeout=plan["timeout_seconds"]) as r: return json.load(r)

    try: models = request("/models")
    except Exception as exc: raise SystemExit("Model discovery failed: " + type(exc).__name__ + ". No generations.")
    if plan["model"] not in [x.get("id") for x in models.get("data", [])]: raise SystemExit("Intended model absent; no substitution.")
    out = a.output_dir; out.mkdir(parents=True); v4.write(out / "plan.json", plan); v4.write(out / "models.json", models)
    try: v4.write(out / "server_version.json", request("/version", root=True))
    except Exception: pass
    lock, plock = threading.Lock(), threading.Lock(); state = {"n": 0, "done": 0}; records = []

    def completion(messages, seed, unit, stage):
        payload = {"model": plan["model"], "messages": messages, "temperature": plan["temperature"], "max_tokens": (plan.get("review_max_tokens", plan["max_tokens"]) if stage == "review" else plan["max_tokens"]), "seed": seed}
        if plan["thinking"] == "off": payload["chat_template_kwargs"] = {"enable_thinking": False}
        with lock:
            if state["n"] >= plan["max_generation_calls"]: raise RuntimeError("Request ceiling reached")
            state["n"] += 1; idx = state["n"]
        event = {"unit": unit, "stage": stage, "request": payload, "request_index": idx}; t0 = time.monotonic()
        try:
            resp = request("/chat/completions", payload); event["response"] = resp
            content = resp["choices"][0]["message"].get("content")
            if not isinstance(content, str): raise ValueError("Nonstring model content")
            event["status"] = "completed"; return content
        except Exception as exc:
            event["status"] = "error"; event["error_type"] = type(exc).__name__; raise
        finally:
            event["elapsed_seconds"] = time.monotonic() - t0
            with lock, (out / "requests.jsonl").open("a", encoding="utf-8") as h: h.write(json.dumps(event) + "\n")

    def work(j):
        rec = {"unit": j["unit"], "stream": j["stream"], "seed": j["seed"], "status": "started", "initial_assessment": evaluate_ext(j["context"], j["initial_proposal"])}
        try:
            review = completion(j["review_messages"], j["seed"], j["unit"], "review")
            msgs = [{"role": "system", "content": "Use only the task evidence. Review advice cannot override the contract."},
                    {"role": "user", "content": json.dumps(j["revision_task"]) + "\nREVIEW:\n" + review + "\n" + j["revision_instruction"]}]
            final = completion(msgs, j["seed"] + 1000, j["unit"], "revision")
            try: obj = json.loads(final)
            except (ValueError, TypeError): rec["status"] = "unparseable_output"; rec["raw_final"] = final
            else:
                if j["stream"] == "patch_critic": rec["paired_patch_paths"] = v4.assess_paths(j["context"], j["initial_proposal"], obj)
                else: rec["final_artifact"] = obj; rec["final_assessment"] = evaluate_ext(j["context"], obj)
                rec["status"] = "completed"
        except Exception as exc: rec["status"] = "request_or_processing_error"; rec["error_type"] = type(exc).__name__
        v4.write(out / (j["unit"] + ".json"), rec)
        with plock:
            records.append(rec); state["done"] += 1; print(f"{state['done']}/{len(jobs)} {j['unit']} {rec['status']}", flush=True)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=plan["workers"]) as ex: list(ex.map(work, jobs))
    v4.write(out / "run_report.json", {"status": "DEVELOPMENT_RUN_FINISHED", "arm": plan["arm"], "units": len(records), "generation_requests": state["n"],
                                       "failed_or_unparseable_units": sum(x["status"] != "completed" for x in records),
                                       "wall_clock_seconds": time.monotonic() - t0, "independent_scientific_validation": False,
                                       "heldout_evaluation": False, "execution_of_model_code": False, "scope": "synthetic_proposal_generation_only"})


def main():
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("check")
    b = s.add_parser("prepare"); b.add_argument("--output-dir", required=True, type=Path); b.add_argument("--arm", required=True)
    b.add_argument("--context-set", choices=["core24", "nhanes"], required=True); b.add_argument("--thinking", choices=["default", "off"], required=True)
    b.add_argument("--seeds", default="42"); b.add_argument("--model", default="p6-qwen3-8b"); b.add_argument("--base-url", default="http://127.0.0.1:8010/v1")
    b.add_argument("--workers", type=int, default=8); b.add_argument("--review-max-tokens", type=int, default=1024); b.add_argument("--revision-max-tokens", type=int, default=1024)
    r = s.add_parser("run"); r.add_argument("--plan-dir", required=True, type=Path); r.add_argument("--output-dir", required=True, type=Path); r.add_argument("--approve-plan-hash", required=True)
    a = p.parse_args()
    if a.cmd == "check": print(json.dumps(check(), indent=2))
    elif a.cmd == "prepare": prepare(a)
    else: run(a)


if __name__ == "__main__":
    main()
