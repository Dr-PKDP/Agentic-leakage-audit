from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.stage9_proposal_validator import validate_proposal


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "configs" / "stage9_adversarial_proposals.yaml"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "outputs"
    / "stage9_runs"
    / "P6_STAGE9_adversarial_guard_report.json"
)


def load_fixtures() -> dict:
    return yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))


def evaluate_fixtures() -> dict:
    config = load_fixtures()
    results = []

    for fixture in config["fixtures"]:
        validation = validate_proposal(fixture["proposal"])
        observed_status = validation["status"]
        expected_status = fixture["expected_status"]

        results.append(
            {
                "id": fixture["id"],
                "expected_status": expected_status,
                "observed_status": observed_status,
                "expectation_matched": (
                    observed_status == expected_status
                ),
                "rationale": fixture["rationale"],
                "validator_details": validation["details"],
            }
        )

    matched = sum(
        item["expectation_matched"]
        for item in results
    )

    return {
        "project": config["project"],
        "stage": config["stage"],
        "task": config["task"],
        "fixture_count": len(results),
        "matched_expectations": matched,
        "overall_status": (
            "pass" if matched == len(results) else "fail"
        ),
        "results": results,
    }


def main() -> None:
    report = evaluate_fixtures()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()