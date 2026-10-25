from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = REPO_ROOT / "configs" / "stage9_agent_benchmark.yaml"
OUTPUT_DIR = REPO_ROOT / "outputs" / "stage9_runs"


def load_benchmark() -> dict:
    return yaml.safe_load(BENCHMARK_PATH.read_text(encoding="utf-8"))


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def build_manifest(
    run_id: str,
    agent_name: str,
    seed: int,
    feature_audit_path: str,
    critic_report_path: str,
    test_labels_accessed: bool,
) -> dict:
    benchmark = load_benchmark()

    return {
        "run_id": run_id,
        "agent_name": agent_name,
        "seed": int(seed),
        "status": "planned",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project": benchmark["project"],
        "stage": benchmark["stage"],
        "task": benchmark["tasks"][0]["name"],
        "training_cycles": benchmark["tasks"][0]["train_cycles"],
        "locked_test_cycle": benchmark["tasks"][0]["temporal_test_cycle"],
        "test_labels_accessed": bool(test_labels_accessed),
        "feature_audit_path": feature_audit_path,
        "critic_report_path": critic_report_path,
        "metrics": {},
        "artifacts": [],
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "pandas_version": pd.__version__,
            "git_commit": git_commit(),
        },
    }


def validate_manifest(manifest: dict) -> dict[str, str]:
    required = [
        "run_id",
        "agent_name",
        "seed",
        "status",
        "task",
        "training_cycles",
        "locked_test_cycle",
        "test_labels_accessed",
        "feature_audit_path",
        "critic_report_path",
    ]
    missing = [field for field in required if field not in manifest]

    if missing:
        return {
            "status": "fail",
            "details": f"Missing required fields: {missing}",
        }

    if manifest["test_labels_accessed"]:
        return {
            "status": "fail",
            "details": "Locked test labels were accessed by this run.",
        }

    if manifest["locked_test_cycle"] in manifest["training_cycles"]:
        return {
            "status": "fail",
            "details": "Locked test cycle overlaps training cycles.",
        }

    return {
        "status": "pass",
        "details": "Manifest is structurally valid and preserves test-label lock.",
    }


def save_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    benchmark = load_benchmark()

    planned_runs = []
    for agent in benchmark["agents"]:
        for index, seed in enumerate(
            benchmark["reporting"]["random_seeds"][: agent["runs"]],
            start=1,
        ):
            run_id = f"{agent['name']}_seed_{seed}"
            manifest = build_manifest(
                run_id=run_id,
                agent_name=agent["name"],
                seed=seed,
                feature_audit_path=(
                    "outputs/features/P6_hypertension_feature_guard_audit.csv"
                ),
                critic_report_path=(
                    "outputs/models/P6_STAGE8_hypertension_critic_report.json"
                ),
                test_labels_accessed=False,
            )

            validation = validate_manifest(manifest)
            manifest["manifest_validation"] = validation
            filename = f"{run_id}_manifest.json"
            save_manifest(manifest, OUTPUT_DIR / filename)

            planned_runs.append(
                {
                    "run_id": run_id,
                    "agent_name": agent["name"],
                    "seed": seed,
                    "status": validation["status"],
                    "manifest_path": str(
                        (OUTPUT_DIR / filename).relative_to(REPO_ROOT)
                    ),
                }
            )

    index = pd.DataFrame(planned_runs)
    index_path = OUTPUT_DIR / "P6_STAGE9_run_manifest_index.csv"
    index.to_csv(index_path, index=False)

    print(index_path)
    print(index.to_string(index=False))


if __name__ == "__main__":
    main()