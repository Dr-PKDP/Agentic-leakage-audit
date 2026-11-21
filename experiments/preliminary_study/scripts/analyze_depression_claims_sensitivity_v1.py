import copy
import csv
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(
    "outputs/agent_comparison/20261025T064454685602Z"
)
RUNNER = Path("scripts/run_depression_agent_comparison_v1.py")
ALLOWED = {
    "no_empirical_claim",
    "internal_development_design_only",
}
CONDITIONS = [
    "single_self_review",
    "structure_feedback",
    "guarded_critic",
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")

config = json.loads((ROOT / "config.json").read_text())
provenance = json.loads((ROOT / "provenance.json").read_text())

if sha(RUNNER) != provenance["script_sha256"]:
    raise SystemExit(
        "Runner changed since the original run. "
        "Stop: recover the original scorer before proceeding."
    )

spec = importlib.util.spec_from_file_location("original_runner", RUNNER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

cases = {case["id"]: case for case in config["cases"]}
events = {}
for line in (ROOT / "requests.jsonl").read_text().splitlines():
    event = json.loads(line)
    if event["stage"] not in {"initial", "final"}:
        continue
    key = (event["unit"], event["stage"])
    if key in events:
        raise SystemExit("Duplicate proposal event: " + str(key))
    events[key] = event

records = [
    json.loads(path.read_text())
    for path in sorted(ROOT.glob("*__*.json"))
]
if len(records) != 45 or len(events) != 90:
    raise SystemExit(
        f"Unexpected inventory: {len(records)} units, "
        f"{len(events)} proposal events."
    )

details = []
drafts = {}
comparison_fields = [
    "structure_valid",
    "structure_findings",
    "contract_assessable",
    "contract_findings",
    "contract_pass",
]

for record in records:
    case = cases[record["case"]]
    detail = {
        "unit": record["unit"],
        "case": record["case"],
        "condition": record["condition"],
        "seed": record["seed"],
    }

    for stage in ("initial", "final"):
        event = events[(record["unit"], stage)]
        text = event["response"]["choices"][0]["message"]["content"]
        strict = module.score(text, case)

        for field in comparison_fields:
            if strict.get(field) != record[stage].get(field):
                raise SystemExit(
                    f"Original-score reproduction mismatch: "
                    f"{record['unit']} {stage} {field}"
                )

        repaired = False
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                claim = obj.get("claims")
                if isinstance(claim, str) and claim in ALLOWED:
                    obj = copy.deepcopy(obj)
                    obj["claims"] = [claim]
                    repaired = True
        except (ValueError, TypeError):
            obj = None

        normalized = (
            module.score(json.dumps(obj), case)
            if repaired else strict
        )

        detail[stage] = {
            "claims_normalized": repaired,
            "strict": strict,
            "normalized": normalized,
        }
        if stage == "initial":
            pair = (record["case"], record["seed"])
            drafts.setdefault(pair, {})[record["condition"]] = text

    details.append(detail)

identity = []
for (case_id, seed), texts in sorted(drafts.items()):
    if set(texts) != set(CONDITIONS):
        raise SystemExit("Missing matched initial draft.")
    identity.append({
        "case": case_id,
        "seed": seed,
        "byte_identical_across_conditions": len(set(texts.values())) == 1,
        "sha256_by_condition": {
            condition: hashlib.sha256(text.encode()).hexdigest()
            for condition, text in texts.items()
        },
    })

summary = []
for case_id in list(cases) + ["ALL"]:
    for condition in CONDITIONS:
        group = [
            item for item in details
            if item["condition"] == condition
            and (case_id == "ALL" or item["case"] == case_id)
        ]
        row = {
            "case": case_id,
            "condition": condition,
            "units": len(group),
        }
        for stage in ("initial", "final"):
            row[stage + "_claims_normalized"] = sum(
                item[stage]["claims_normalized"] for item in group
            )
            for mode in ("strict", "normalized"):
                row[stage + "_" + mode + "_pass"] = sum(
                    item[stage][mode]["contract_pass"] for item in group
                )

        row["normalized_revision_improvements"] = sum(
            not item["initial"]["normalized"]["contract_pass"]
            and item["final"]["normalized"]["contract_pass"]
            for item in group
        )
        row["normalized_revision_regressions"] = sum(
            item["initial"]["normalized"]["contract_pass"]
            and not item["final"]["normalized"]["contract_pass"]
            for item in group
        )
        summary.append(row)

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
out = ROOT / ("posthoc_claims_sensitivity_" + stamp)
out.mkdir(exist_ok=False)

with (out / "summary.csv").open(
    "x", newline="", encoding="utf-8"
) as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)

write_json(out / "details.json", details)
write_json(out / "initial_draft_identity.json", identity)

report = {
    "status": "COMPLETED_POSTHOC_ARTIFACT_ANALYSIS",
    "source_run": str(ROOT),
    "source_requests_sha256": sha(ROOT / "requests.jsonl"),
    "original_runner_sha256": sha(RUNNER),
    "analysis_script_sha256": sha(Path(__file__)),
    "original_scores_reproduced": True,
    "new_model_requests": 0,
    "participant_data_access": False,
    "normalization_rule": (
        "Convert a scalar claims string to a singleton list "
        "only when it exactly matches an allowed claim label. "
        "No other changes."
    ),
    "matched_initial_draft_groups": len(identity),
    "byte_identical_initial_draft_groups": sum(
        item["byte_identical_across_conditions"] for item in identity
    ),
    "aggregate": [
        row for row in summary if row["case"] == "ALL"
    ],
    "output_directory": str(out),
    "limitations": [
        "Post hoc analysis motivated by observed outputs.",
        "Original strict scores remain the primary reported result.",
        "Normalized scores still assess contract compliance, "
        "not independent scientific validity.",
        "No new model generations or modified original artifacts.",
    ],
}
write_json(out / "run_report.json", report)
print(json.dumps(report, indent=2))
