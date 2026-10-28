import json
import os
import subprocess
import sys
from pathlib import Path

import mock_server
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "experiments/extended_v0_5"
ENV = {
    **os.environ,
    "PYTHONPATH": os.pathsep.join(
        [str(ROOT / "experiments/principal_v0_4"), os.environ.get("PYTHONPATH", "")]
    ),
}


def run(*args):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        cwd=EXT,
        env=ENV,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_offline_check_passes():
    assert json.loads(run("p6_extended_v0_5.py", "check"))


@pytest.mark.parametrize(
    "context_set,thinking", [("nhanes", "off"), ("core24", "default")]
)
def test_prepare_run_analyze_roundtrip(tmp_path, context_set, thinking):
    server = mock_server.start("oracle")
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}/v1"
        plan, runs, analysis = (
            tmp_path / "plan",
            tmp_path / "run",
            tmp_path / "analysis",
        )
        prepared = json.loads(
            run(
                "p6_extended_v0_5.py",
                "prepare",
                "--output-dir",
                plan,
                "--arm",
                "t",
                "--context-set",
                context_set,
                "--thinking",
                thinking,
                "--seeds",
                "42",
                "--model",
                "mock-model",
                "--base-url",
                base,
                "--workers",
                "4",
            )
        )
        run(
            "p6_extended_v0_5.py",
            "run",
            "--plan-dir",
            plan,
            "--output-dir",
            runs,
            "--approve-plan-hash",
            prepared["plan_sha256"],
        )
        run(
            "p6_extended_analyze.py",
            "--plan-dir",
            plan,
            "--run-dir",
            runs,
            "--out-dir",
            analysis,
        )
        summary = json.loads((analysis / "summary.json").read_text())
        assert summary["arm"] == "t" and summary["by_path"]
        requests = sum(v["n"] for v in summary["requests"].values())
        assert requests == prepared["max_generation_calls"]
    finally:
        server.shutdown()


def test_run_refuses_wrong_plan_hash(tmp_path):
    plan = tmp_path / "plan"
    run(
        "p6_extended_v0_5.py",
        "prepare",
        "--output-dir",
        plan,
        "--arm",
        "t",
        "--context-set",
        "core24",
        "--thinking",
        "off",
        "--seeds",
        "42",
        "--model",
        "m",
        "--base-url",
        "http://127.0.0.1:9/v1",
        "--workers",
        "1",
    )
    result = subprocess.run(
        [
            sys.executable,
            "p6_extended_v0_5.py",
            "run",
            "--plan-dir",
            str(plan),
            "--output-dir",
            str(tmp_path / "r"),
            "--approve-plan-hash",
            "0" * 64,
        ],
        cwd=EXT,
        env=ENV,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
