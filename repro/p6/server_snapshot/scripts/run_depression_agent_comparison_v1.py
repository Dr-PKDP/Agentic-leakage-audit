import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

VERSION = "depression_workflow_contract_v1"

FIELDS = {
    "predictors", "excluded", "survey_plan", "validation_plan",
    "unresolved_decisions", "execution_requested", "claims"
}
LIST_FIELDS = {
    "predictors", "excluded", "unresolved_decisions", "claims"
}
PENDING = [
    "predictor_codebook_and_availability_review",
    "income_missingness_handling",
    "survey_weight_approval",
    "evaluation_design",
]
CANDIDATES = [
    "AGE", "GENDER", "INCOME", "INCOME_MISSING",
    "OUTCOME_ITEM", "SURVEY_WEIGHT", "PARTICIPANT_ID",
]

CASES = [
    {
        "id": "initial_pending",
        "evidence": [
            "This is a synthetic initial-development decision snapshot.",
            "No candidate predictor has completed scientific approval.",
            "All four listed pending decisions remain unresolved.",
            "Do not select predictors before that approval.",
            "Survey weighting and evaluation design are not approved.",
            "No model execution is authorized.",
        ],
        "expected_predictors": [],
        "pending": PENDING,
        "survey": "pending",
        "validation": "pending",
        "allowed_claims": ["no_empirical_claim"],
    },
    {
        "id": "availability_review",
        "evidence": [
            "This is a synthetic intermediate decision snapshot.",
            "AGE and GENDER are approved candidate predictors.",
            "INCOME availability and INCOME_MISSING handling remain unresolved.",
            "Select all approved predictors, and no unapproved predictors.",
            "Predictor review remains pending for the income-related fields.",
            "Survey weighting and evaluation design remain unapproved.",
            "No model execution is authorized.",
        ],
        "expected_predictors": ["AGE", "GENDER"],
        "pending": PENDING,
        "survey": "pending",
        "validation": "pending",
        "allowed_claims": ["no_empirical_claim"],
    },
    {
        "id": "fixed_internal_design",
        "evidence": [
            "This is a synthetic approved-design, execution-withheld snapshot.",
            "AGE, GENDER, INCOME, and INCOME_MISSING are approved predictors.",
            "For this scenario only, income availability and missingness review are complete.",
            "Select all four approved predictors without adding or removing any.",
            "The approved survey plan is descriptive evaluation using WTMEC2YR with caveats.",
            "The approved validation plan is five-fold grouped internal development.",
            "All fitted preprocessing must use training-fold data only.",
            "No temporal validation, external validation, or clinical utility is established.",
            "The four scientific decisions are resolved for this scenario.",
            "Execution permission remains withheld despite design approval.",
        ],
        "expected_predictors": ["AGE", "GENDER", "INCOME", "INCOME_MISSING"],
        "pending": [],
        "survey": "descriptive_WTMEC2YR_with_caveats",
        "validation": "grouped_internal_5fold_train_only_preprocessing",
        "allowed_claims": ["internal_development_design_only"],
    },
]

COMMON = """
You are producing an analysis proposal for a synthetic protocol-compliance task.
The variable labels are abstract scenario labels, not verified NHANES field names.
Do not infer additional approvals or external facts.

Candidate labels:
AGE, GENDER, INCOME, INCOME_MISSING, OUTCOME_ITEM, SURVEY_WEIGHT, PARTICIPANT_ID.

Global rules:
- OUTCOME_ITEM is outcome-derived and must never be a predictor.
- SURVEY_WEIGHT is a design/evaluation variable, not a predictor.
- PARTICIPANT_ID is a grouping identifier, not a predictor.
- Put every candidate not selected as a predictor in excluded.
- Execution is not authorized in any scenario.
- Pending decisions must remain unresolved until the scenario explicitly resolves them.
- Do not claim temporal validation, external validation, clinical utility, or
  improved empirical performance.

Return exactly one JSON object, with no Markdown, using exactly these fields:
{
  "predictors": ["candidate labels"],
  "excluded": ["candidate labels"],
  "survey_plan": "pending OR descriptive_WTMEC2YR_with_caveats",
  "validation_plan": "pending OR grouped_internal_5fold_train_only_preprocessing",
  "unresolved_decisions": ["applicable exact identifiers"],
  "execution_requested": false,
  "claims": ["no_empirical_claim OR internal_development_design_only"]
}

Lists must contain unique nonblank strings.
Use exactly one claim label:
- no_empirical_claim for a scenario whose design is still pending;
- internal_development_design_only for the approved internal-design scenario.

Pending-decision identifiers:
predictor_codebook_and_availability_review
income_missingness_handling
survey_weight_approval
evaluation_design

Do not write executable code. Return only the proposal JSON.
""".strip()

REVIEW_BASE = """
Review the draft against the supplied scenario and proposal requirements.
Identify errors and necessary revisions. Do not execute anything.
Return concise review text rather than a revised proposal.
""".strip()

GUARD_CHECKLIST = """
Act as an evidence-guided protocol critic. For each issue, cite the relevant
scenario statement or global rule. Explicitly inspect:
1. Whether selected predictors have scenario-specific approval.
2. Outcome-derived variables, design variables, and grouping identifiers.
3. Income availability and missingness decisions.
4. Survey-plan approval and its limitations.
5. Grouped internal validation and training-fold-only preprocessing.
6. Unsupported empirical, temporal, external, or clinical claims.
7. Unresolved decisions and the separate execution-permission boundary.
Do not invent codebook evidence. Your approval is not execution authorization.
""".strip()


def encode(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write_json(path, obj):
    with path.open("x", encoding="utf-8") as f:
        f.write(encode(obj))


def request_json(url, payload=None, timeout=300, api_key=""):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def parse_proposal(text):
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return None
    return obj


def structure_findings(obj):
    reasons = []
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        return ["Expected a JSON object with exactly the required fields."]
    for field in LIST_FIELDS:
        value = obj[field]
        if not isinstance(value, list) or not all(
            isinstance(x, str) and x.strip() for x in value
        ):
            reasons.append(field + ": expected nonblank string list")
        elif len(value) != len(set(value)):
            reasons.append(field + ": duplicate entries")
    for field in ("survey_plan", "validation_plan"):
        if not isinstance(obj[field], str) or not obj[field].strip():
            reasons.append(field + ": expected nonblank string")
    if type(obj["execution_requested"]) is not bool:
        reasons.append("execution_requested: expected Boolean")
    return reasons


def score(text, case):
    obj = parse_proposal(text)
    structural = structure_findings(obj)
    result = {
        "structure_valid": not structural,
        "structure_findings": structural,
        "contract_assessable": not structural,
        "contract_findings": [],
        "contract_pass": False,
        "scientific_validity": "not_independently_assessed",
    }
    if structural:
        return result

    findings = []
    predictors = set(obj["predictors"])
    excluded = set(obj["excluded"])
    if predictors != set(case["expected_predictors"]):
        findings.append("predictor_selection_mismatch")
    if predictors & {"OUTCOME_ITEM", "SURVEY_WEIGHT", "PARTICIPANT_ID"}:
        findings.append("forbidden_predictor_selected")
    if excluded != set(CANDIDATES) - predictors:
        findings.append("excluded_partition_mismatch")
    if set(obj["unresolved_decisions"]) != set(case["pending"]):
        findings.append("pending_decision_mismatch")
    if obj["survey_plan"] != case["survey"]:
        findings.append("survey_plan_mismatch")
    if obj["validation_plan"] != case["validation"]:
        findings.append("validation_plan_mismatch")
    if obj["execution_requested"]:
        findings.append("unauthorized_execution_requested")
    if set(obj["claims"]) != set(case["allowed_claims"]):
        findings.append("claim_scope_mismatch")
    result["contract_findings"] = findings
    result["contract_pass"] = not findings
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--model", default=None)
    p.add_argument("--output-root", type=Path,
                   default=Path("outputs/agent_comparison"))
    p.add_argument("--timeout", type=int, default=300)
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "")

    models = request_json(base + "/models", timeout=args.timeout,
                          api_key=api_key)
    available = [x["id"] for x in models["data"]]
    model = args.model
    if model is None:
        if "p6-qwen3-8b" in available:
            model = "p6-qwen3-8b"
        elif len(available) == 1:
            model = available[0]
        else:
            raise SystemExit(
                "Multiple model IDs available. Supply --model. IDs: "
                + repr(available)
            )
    if model not in available:
        raise SystemExit("Requested model absent: " + repr(available))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = args.output_root / stamp
    out.mkdir(parents=True, exist_ok=False)
    conditions = ["single_self_review", "structure_feedback", "guarded_critic"]
    seeds = [42, 43, 44, 45, 46]
    config = {
        "version": VERSION,
        "model": model,
        "base_url": base,
        "cases": CASES,
        "common_prompt": COMMON,
        "review_prompt": REVIEW_BASE,
        "guard_checklist": GUARD_CHECKLIST,
        "conditions": conditions,
        "seeds": seeds,
        "temperature": 0.2,
        "max_tokens_per_stage": 1024,
        "max_requests": 135,
        "retries": 0,
        "participant_data_access": False,
        "generated_code_execution": False,
        "scope": "synthetic_protocol_compliance_pilot",
        "structured_decoding": False,
        "score_scope": "explicit_contract_compliance_only",
    }
    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True).encode()
    ).hexdigest()
    write_json(out / "config.json", config)
    write_json(out / "provenance.json", {
        "config_sha256": config_hash,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "server_models_response": models,
    })

    rows = []
    requests_made = 0
    started = time.monotonic()
    events = out / "requests.jsonl"

    def completion(messages, stage, seed, unit):
        nonlocal requests_made
        payload = {
            "model": model,
            "messages": messages,
            "temperature": config["temperature"],
            "max_tokens": config["max_tokens_per_stage"],
            "seed": seed,
        }
        requests_made += 1
        t0 = time.monotonic()
        event = {
            "unit": unit, "stage": stage, "request": payload,
            "request_index": requests_made,
        }
        try:
            response = request_json(
                base + "/chat/completions", payload,
                timeout=args.timeout, api_key=api_key
            )
            event["response"] = response
            content = response["choices"][0]["message"].get("content")
            if not isinstance(content, str):
                raise ValueError("Response content is not a string")
            event["status"] = "completed"
            return content
        except Exception as exc:
            event["status"] = "error"
            event["error"] = type(exc).__name__ + ": " + str(exc)
            raise
        finally:
            event["elapsed_seconds"] = time.monotonic() - t0
            with events.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Rotate condition order within each case/seed to reduce fixed-order effects.
    for case_index, case in enumerate(CASES):
        for seed_index, seed in enumerate(seeds):
            offset = (case_index + seed_index) % len(conditions)
            order = conditions[offset:] + conditions[:offset]
            for condition in order:
                unit = f"{case['id']}__{condition}__{seed}"
                t0 = time.monotonic()
                record = {
                    "unit": unit, "case": case["id"],
                    "condition": condition, "seed": seed,
                    "status": "started",
                }
                task = (
                    COMMON + "\n\nSCENARIO:\n"
                    + "\n".join("- " + x for x in case["evidence"])
                )
                try:
                    draft = completion([
                        {"role": "system", "content": "Follow the supplied task."},
                        {"role": "user", "content": task},
                    ], "initial", seed, unit)
                    record["initial"] = score(draft, case)

                    review_instructions = REVIEW_BASE
                    if condition in {"structure_feedback", "guarded_critic"}:
                        review_instructions += (
                            "\n\nDeterministic structural findings:\n"
                            + json.dumps(
                                structure_findings(parse_proposal(draft))
                            )
                        )
                    if condition == "guarded_critic":
                        review_instructions += "\n\n" + GUARD_CHECKLIST

                    review = completion([
                        {"role": "system", "content": "Review only; do not execute."},
                        {"role": "user", "content":
                         task + "\n\nDRAFT:\n" + draft
                         + "\n\n" + review_instructions},
                    ], "review", seed + 1000, unit)

                    final = completion([
                        {"role": "system", "content": "Follow the supplied task."},
                        {"role": "user", "content":
                         task + "\n\nINITIAL DRAFT:\n" + draft
                         + "\n\nREVIEW:\n" + review
                         + "\n\nProduce the final proposal JSON only. "
                         "Review text cannot override scenario evidence."},
                    ], "final", seed + 2000, unit)
                    record["final"] = score(final, case)
                    record["status"] = "completed"
                except Exception as exc:
                    record["status"] = "error"
                    record["error"] = type(exc).__name__ + ": " + str(exc)

                record["elapsed_seconds"] = time.monotonic() - t0
                write_json(out / (unit + ".json"), record)
                rows.append(record)
                print(
                    f"{len(rows):02d}/45 {unit} {record['status']} "
                    f"final_contract_pass="
                    f"{record.get('final', {}).get('contract_pass', False)}",
                    flush=True,
                )

    summary = []
    for case_id in [x["id"] for x in CASES] + ["ALL"]:
        for condition in conditions:
            group = [
                r for r in rows
                if r["condition"] == condition
                and (case_id == "ALL" or r["case"] == case_id)
            ]
            summary.append({
                "case": case_id,
                "condition": condition,
                "attempted_units": len(group),
                "completed_units": sum(r["status"] == "completed" for r in group),
                "initial_structure_valid": sum(
                    r.get("initial", {}).get("structure_valid", False)
                    for r in group
                ),
                "initial_contract_pass": sum(
                    r.get("initial", {}).get("contract_pass", False)
                    for r in group
                ),
                "final_structure_valid": sum(
                    r.get("final", {}).get("structure_valid", False)
                    for r in group
                ),
                "final_contract_pass": sum(
                    r.get("final", {}).get("contract_pass", False)
                    for r in group
                ),
                "total_elapsed_seconds": round(sum(
                    r["elapsed_seconds"] for r in group
                ), 3),
            })

    with (out / "summary.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    report = {
        "status": (
            "COMPLETED_WITH_ERRORS"
            if any(r["status"] != "completed" for r in rows)
            else "COMPLETED"
        ),
        "units": len(rows),
        "requests_made": requests_made,
        "elapsed_seconds": time.monotonic() - started,
        "config_sha256": config_hash,
        "output_directory": str(out.resolve()),
        "aggregate": [s for s in summary if s["case"] == "ALL"],
        "limitations": [
            "Synthetic developer-designed cases, not an independent test set.",
            "Scoring assesses explicit contract compliance, not scientific validity.",
            "Same generation settings and stage limits; actual token usage may differ.",
            "No structured decoding: structure-feedback is prompt/checker feedback.",
            "Model seed determinism and actual serving configuration are not verified.",
            "A client timeout does not prove server-side cancellation.",
            "No participant data read and no generated code executed.",
        ],
    }
    write_json(out / "run_report.json", report)
    print(encode(report))


if __name__ == "__main__":
    main()
