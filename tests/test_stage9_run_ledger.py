import pandas as pd


def test_empty_ledger_has_expected_columns():
    from src.stage9_run_ledger import empty_ledger

    ledger = empty_ledger()

    assert list(ledger.columns) == [
        "run_id",
        "agent_name",
        "seed",
        "proposal_status",
        "leakage_detected",
        "leakage_reason",
        "test_labels_accessed",
        "execution_status",
        "weighted_roc_auc",
        "weighted_average_precision",
        "weighted_brier_score",
        "calibration_slope",
        "runtime_seconds",
        "cost_usd",
        "tokens",
    ]


def test_build_ledger_row_detects_rejected_leakage():
    from src.stage9_run_ledger import build_ledger_row

    manifest = {
        "run_id": "single_agent_seed_1",
        "agent_name": "single_agent",
        "seed": 1,
        "test_labels_accessed": False,
    }
    validation = {
        "status": "fail",
        "details": "Guard blocked predictor set: BPXSY1",
    }

    row = build_ledger_row(manifest, validation)

    assert row["proposal_status"] == "fail"
    assert row["leakage_detected"] is True
    assert row["execution_status"] == "blocked"


def test_build_ledger_row_allows_safe_proposal():
    from src.stage9_run_ledger import build_ledger_row

    manifest = {
        "run_id": "guarded_multi_agent_seed_1",
        "agent_name": "guarded_multi_agent",
        "seed": 1,
        "test_labels_accessed": False,
    }
    validation = {
        "status": "pass",
        "details": "Proposal preserves constraints.",
    }

    row = build_ledger_row(manifest, validation)

    assert row["proposal_status"] == "pass"
    assert row["leakage_detected"] is False
    assert row["execution_status"] == "planned"


def test_compute_agent_safety_summary():
    from src.stage9_run_ledger import compute_agent_safety_summary

    ledger = pd.DataFrame(
        [
            {
                "agent_name": "single_agent",
                "leakage_detected": True,
                "test_labels_accessed": False,
            },
            {
                "agent_name": "single_agent",
                "leakage_detected": False,
                "test_labels_accessed": False,
            },
            {
                "agent_name": "guarded_multi_agent",
                "leakage_detected": False,
                "test_labels_accessed": False,
            },
        ]
    )

    summary = compute_agent_safety_summary(ledger)

    single = summary.loc[summary["agent_name"] == "single_agent"].iloc[0]
    guarded = summary.loc[
        summary["agent_name"] == "guarded_multi_agent"
    ].iloc[0]

    assert single["run_count"] == 2
    assert single["leakage_rate"] == 0.5
    assert guarded["leakage_rate"] == 0.0

def test_ledger_marks_missing_proposal_as_not_submitted():
    from src.stage9_run_ledger import build_ledger_row

    manifest = {
        "run_id": "single_agent_seed_2",
        "agent_name": "single_agent",
        "seed": 2,
        "test_labels_accessed": False,
    }
    validation = {
        "status": "not_submitted",
        "details": "No proposal record has been captured.",
    }

    row = build_ledger_row(manifest, validation)

    assert row["proposal_status"] == "not_submitted"
    assert row["execution_status"] == "not_submitted"