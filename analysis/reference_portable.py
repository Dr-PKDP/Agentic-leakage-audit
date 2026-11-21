"""Optional refit of the fixed reference on the public NHANES 2017-2018 files. Not part of the default replay."""

import ast, hashlib, importlib.metadata, json, os, shutil, subprocess, sys
from pathlib import Path


def report(base):
    return json.loads(
        (
            base
            / "experiments/preliminary_study/outputs/reference_evaluation/depression_20261025T063110357273Z/run_report.json"
        ).read_text()
    )


def check_inputs(base, demo, dpq):
    r = report(base)
    checks = {}
    for name, path in [("DEMO_J", demo), ("DPQ_J", dpq)]:
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if digest != r["input_sha256"][name]:
            raise ValueError("Public input checksum differs from recorded run: " + name)
        checks[name] = digest
    return {"status": "RECORDED_PUBLIC_INPUT_HASHES_MATCH", "sha256": checks, "fit_performed": False}


def refit(base, demo, dpq, out):
    if out.exists():
        raise ValueError("Output exists; choose a new --out")
    check_inputs(base, demo, dpq)
    expected = report(base)
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Reference environment requires Python 3.11; use the recorded dependency file")
    for package, key in [
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("scikit-learn", "scikit_learn"),
        ("pyreadstat", "pyreadstat"),
    ]:
        if importlib.metadata.version(package) != expected["versions"][key]:
            raise ValueError("Reference package mismatch: " + package)
    out.mkdir(parents=True)
    workspace = out / "workspace"
    shutil.copytree(base / "experiments/preliminary_study", workspace)
    raw = workspace / "data/raw/nhanes/2017_2018"
    raw.mkdir(parents=True)
    shutil.copyfile(demo, raw / "DEMO_J.xpt")
    shutil.copyfile(dpq, raw / "DPQ_J.xpt")
    env = os.environ.copy()
    env["P6_DIR"] = str(workspace.resolve())
    # Regenerate a real aggregate predictor/fold audit from the same public inputs.
    audit = subprocess.run(
        [sys.executable, str((workspace / "scripts/audit_depression_predictors_v5.py").resolve())],
        env=env,
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    (out / "predictor_audit_stdout.txt").write_text(audit.stdout)
    (out / "predictor_audit_stderr.txt").write_text(audit.stderr)
    if audit.returncode:
        raise RuntimeError(
            "Predictor audit failed; no reference fit attempted. Inspect the saved aggregate diagnostic."
        )
    audits = list((workspace / "outputs/data_inspection").glob("depression_predictor_fold_audit_*.json"))
    if len(audits) != 1:
        raise RuntimeError("Expected exactly one freshly generated predictor audit")
    fresh = audits[0].resolve()
    a = json.loads(fresh.read_text())
    if a["status"] != "PASS_AUDIT_ONLY":
        raise RuntimeError("Fresh predictor audit did not pass")
    frozen = workspace / "scripts/run_depression_reference_v1.py"
    tree = ast.parse(frozen.read_text())
    edits = {"ROOT": 0, "old_audit_path": 0}
    # Adapt paths only; do not alter outcomes, folds, preprocessing, estimator or scoring.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key = node.targets[0].id
            if key in edits:
                node.value = ast.Call(
                    func=ast.Name(id="Path", ctx=ast.Load()),
                    args=[ast.Constant(str(workspace.resolve() if key == "ROOT" else fresh))],
                    keywords=[],
                )
                edits[key] += 1
    if edits != {"ROOT": 1, "old_audit_path": 1}:
        raise RuntimeError("Path adapter did not match the frozen source; no fit attempted")
    ast.fix_missing_locations(tree)
    config = workspace / "configs/nhanes_depression_dev_v7.json"
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    if digest != expected["config_sha256"]:
        raise RuntimeError("Frozen config changed")
    sys.argv = [str(frozen), "--config-sha256", digest]
    # The original runner checks source, cohort and all folds before fitting.
    exec(compile(tree, str(frozen), "exec"), {"__name__": "__main__", "__file__": str(frozen)})
    results = [
        p
        for p in (workspace / "outputs/reference_evaluation").glob("depression_*/run_report.json")
        if p.parent.name != "depression_20261025T063110357273Z"
    ]
    if len(results) != 1:
        raise RuntimeError("Expected one new reference report")
    actual = json.loads(results[0].read_text())
    matches = []
    for old, new in zip(expected["metrics"], actual.get("metrics", [])):
        if (old["arm"], old["weighting"]) != (new["arm"], new["weighting"]):
            raise RuntimeError("Metric alignment differs")
        matches.append(all(abs(old[k] - new[k]) <= 1e-10 for k in ("AUROC", "Brier", "log_loss")))
    summary = {
        "status": actual["status"],
        "new_local_reference_fit": True,
        "model_API_calls": 0,
        "metrics_match_within_1e_10": len(matches) == 6 and all(matches),
        "path_adapter": edits,
        "fresh_prior_audit": str(fresh),
        "source_algorithm_unchanged": True,
        "original_timestamp_and_prior_audit_hash_not_reproduced": True,
        "new_report": str(results[0]),
    }
    (out / "portable_reference_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
