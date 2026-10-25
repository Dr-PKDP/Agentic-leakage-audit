from __future__ import annotations

from pathlib import Path

import yaml

from src.feature_guard import assert_predictors_allowed


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = REPO_ROOT / "configs" / "stage9_agent_benchmark.yaml"

REQUIRED_FIELDS = [
    "run_id",
    "agent_name",
    "seed",
    "predictors",
    "target",
    "training_cycles",
    "evaluation_cycle",
    "request_test_labels",
    "model",
]


def load_benchmark() -> dict:
    return yaml.safe_load(BENCHMARK_PATH.read_text(encoding="utf-8"))


def validate_proposal(proposal: dict) -> dict[str, str]:
    missing = [
        field
        for field in REQUIRED_FIELDS
        if field not in proposal
    ]
    if missing:
        return {
            "status": "fail",
            "details": f"Missing required fields: {missing}",
        }

    benchmark = load_benchmark()
    task = benchmark["tasks"][0]

    if proposal["target"] != task["target"]:
        return {
            "status": "fail",
            "details": (
                f"Target must be '{task['target']}', "
                f"not '{proposal['target']}'."
            ),
        }

    if proposal["request_test_labels"]:
        return {
            "status": "fail",
            "details": "Proposal requests locked evaluation labels.",
        }

    if proposal["evaluation_cycle"] != task["temporal_test_cycle"]:
        return {
            "status": "fail",
            "details": (
                "Proposal evaluation cycle does not match the locked "
                f"test cycle '{task['temporal_test_cycle']}'."
            ),
        }

    if proposal["evaluation_cycle"] in proposal["training_cycles"]:
        return {
            "status": "fail",
            "details": "Evaluation cycle overlaps training cycles.",
        }

    allowed_train_cycles = set(task["train_cycles"])
    requested_train_cycles = set(proposal["training_cycles"])
    unexpected_cycles = requested_train_cycles - allowed_train_cycles

    if unexpected_cycles:
        return {
            "status": "fail",
            "details": (
                "Training cycles are outside the benchmark protocol: "
                f"{sorted(unexpected_cycles)}"
            ),
        }

    try:
        assert_predictors_allowed(proposal["predictors"])
    except ValueError as error:
        return {
            "status": "fail",
            "details": str(error),
        }

    return {
        "status": "pass",
        "details": (
            "Proposal preserves feature, survey, temporal, and "
            "test-label constraints."
        ),
    }