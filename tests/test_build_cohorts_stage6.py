import pytest

from src.build_cohorts_stage6 import egfr_2021_ckd_epi, mean_valid_bp


def test_egfr_2021_ckd_epi_reference_values():
    female_value = egfr_2021_ckd_epi(
        serum_creatinine_mg_dl=1.0,
        age_years=50,
        sex="female",
    )

    assert female_value == pytest.approx(68.6, abs=0.2)


def test_mean_valid_systolic_bp_ignores_zero_and_missing():
    assert mean_valid_bp([120, 0, None, 130], allow_zero=False) == pytest.approx(125.0)


def test_mean_valid_diastolic_bp_retains_zero():
    assert mean_valid_bp([80, 0, None, 90], allow_zero=True) == pytest.approx(170 / 3)


def test_mean_valid_bp_returns_none_when_no_values_remain():
    assert mean_valid_bp([None, 0, float("nan")], allow_zero=False) is None


def test_has_elevated_bp_at_130_80():
    from src.build_cohorts_stage6 import has_elevated_bp

    assert has_elevated_bp(mean_systolic=130.0, mean_diastolic=79.9) is True
    assert has_elevated_bp(mean_systolic=129.9, mean_diastolic=80.0) is True
    assert has_elevated_bp(mean_systolic=129.9, mean_diastolic=79.9) is False
    assert has_elevated_bp(mean_systolic=None, mean_diastolic=80.0) is None


def test_normalize_nhanes_yes_no_unknown():
    from src.build_cohorts_stage6 import normalize_nhanes_yes_no

    assert normalize_nhanes_yes_no(1) is True
    assert normalize_nhanes_yes_no(2) is False
    assert normalize_nhanes_yes_no(7) is None
    assert normalize_nhanes_yes_no(9) is None
    assert normalize_nhanes_yes_no(None) is None


def test_undiagnosed_hypertension_requires_confirmed_no_diagnosis_and_no_medication():
    from src.build_cohorts_stage6 import undiagnosed_hypertension_label

    assert undiagnosed_hypertension_label(True, False, False) == 1
    assert undiagnosed_hypertension_label(False, False, False) == 0
    assert undiagnosed_hypertension_label(True, True, False) == 0
    assert undiagnosed_hypertension_label(True, False, True) == 0
    assert undiagnosed_hypertension_label(True, None, False) is None
    assert undiagnosed_hypertension_label(True, False, None) is None


def test_build_hypertension_row_marks_confirmed_undiagnosed_case():
    from src.build_cohorts_stage6 import build_hypertension_row

    row = build_hypertension_row({
        "SEQN": 1001,
        "RIDAGEYR": 55,
        "RIAGENDR": 2,
        "WTMEC2YR": 1234.5,
        "SDMVPSU": 1,
        "SDMVSTRA": 120,
        "BPXSY1": 132,
        "BPXSY2": 130,
        "BPXSY3": 132,
        "BPXDI1": 78,
        "BPXDI2": 80,
        "BPXDI3": 82,
        "BPQ020": 2,
        "BPQ040A": 2,
    })

    assert row["mean_systolic_bp"] == pytest.approx(131.0)
    assert row["mean_diastolic_bp"] == pytest.approx(81.0)
    assert row["elevated_bp_130_80"] is True
    assert row["known_hypertension"] is False
    assert row["taking_hypertension_medication"] is False
    assert row["undiagnosed_hypertension"] == 1
    assert row["outcome_missing_reason"] is None



def test_hypertension_row_uses_bpq150_when_present():
    from src.build_cohorts_stage6 import build_hypertension_row

    row = build_hypertension_row({
        "SEQN": 2001,
        "BPXSY1": 140,
        "BPXSY2": 138,
        "BPXSY3": 136,
        "BPXDI1": 90,
        "BPXDI2": 88,
        "BPXDI3": 86,
        "BPQ020": 2,
        "BPQ040A": None,
        "BPQ150": 2,
    })

    assert row["taking_hypertension_medication"] is False
    assert row["undiagnosed_hypertension"] == 1




def test_hypertension_source_config_has_four_cycles():
    from src.build_cohorts_stage6 import HYPERTENSION_SOURCE_FILES

    assert set(HYPERTENSION_SOURCE_FILES) == {
        "2011-2012",
        "2013-2014",
        "2015-2016",
        "2021-2023",
    }

    for sources in HYPERTENSION_SOURCE_FILES.values():
        assert set(sources) == {"demo", "bpx", "bpq"}
        assert all(path.suffix.lower() == ".xpt" for path in sources.values())


def test_hypertension_cycle_spec_uses_oscillometric_columns_for_2021_2023():
    from src.build_cohorts_stage6 import HYPERTENSION_CYCLE_SPECS

    spec = HYPERTENSION_CYCLE_SPECS["2021-2023"]

    assert spec["systolic_columns"] == ["BPXOSY1", "BPXOSY2", "BPXOSY3"]
    assert spec["diastolic_columns"] == ["BPXODI1", "BPXODI2", "BPXODI3"]
    assert spec["medication_column"] == "BPQ150"


def test_merge_hypertension_components_rejects_duplicate_seqn():
    import pandas as pd
    import pytest
    from src.build_cohorts_stage6 import merge_hypertension_components

    demo = pd.DataFrame({"SEQN": [1, 2], "RIDAGEYR": [40, 50]})
    bpx = pd.DataFrame({"SEQN": [1, 1], "BPXSY1": [120, 121]})
    bpq = pd.DataFrame({"SEQN": [1, 2], "BPQ020": [2, 2]})

    with pytest.raises(ValueError, match="duplicate SEQN"):
        merge_hypertension_components(demo, bpx, bpq)


def test_load_hypertension_cycle_reads_validated_2015_2016_sources():
    from src.build_cohorts_stage6 import load_hypertension_cycle

    merged = load_hypertension_cycle("2015-2016")

    assert len(merged) > 9000
    assert merged["SEQN"].is_unique
    assert set(merged["nhanes_cycle"]) == {"2015-2016"}
    assert {"RIDAGEYR", "BPXSY1", "BPQ020", "BPQ040A"}.issubset(merged.columns)


def test_build_hypertension_rows_harmonizes_2021_2023_oscillometric_bp():
    import pandas as pd
    from src.build_cohorts_stage6 import build_hypertension_rows

    merged = pd.DataFrame([{
        "SEQN": 3001,
        "RIDAGEYR": 60,
        "BPXOSY1": 142,
        "BPXOSY2": 140,
        "BPXOSY3": 138,
        "BPXODI1": 88,
        "BPXODI2": 86,
        "BPXODI3": 84,
        "BPQ020": 2,
        "BPQ150": 2,
    }])

    rows = build_hypertension_rows(merged, "2021-2023")

    assert len(rows) == 1
    assert rows[0]["SEQN"] == 3001
    assert rows[0]["mean_systolic_bp"] == pytest.approx(139.0)
    assert rows[0]["mean_diastolic_bp"] == pytest.approx(85.0)
    assert rows[0]["undiagnosed_hypertension"] == 1


def test_hypertension_row_excludes_treated_participant_from_undiagnosed_case():
    import pandas as pd
    from src.build_cohorts_stage6 import build_hypertension_row

    row = pd.Series({
        "SEQN": 4001,
        "RIDAGEYR": 58,
        "BPXSY1": 146,
        "BPXSY2": 144,
        "BPXSY3": 142,
        "BPXDI1": 92,
        "BPXDI2": 90,
        "BPXDI3": 88,
        "BPQ020": 2,
        "BPQ150": 1,
    })

    result = build_hypertension_row(row)

    assert result["mean_systolic_bp"] == pytest.approx(143.0)
    assert result["mean_diastolic_bp"] == pytest.approx(89.0)
    assert result["undiagnosed_hypertension"] == 0



def test_build_hypertension_rows_preserves_cycle_on_each_row():
    import pandas as pd
    from src.build_cohorts_stage6 import build_hypertension_rows

    merged = pd.DataFrame([{
        "SEQN": 5001,
        "RIDAGEYR": 52,
        "BPXSY1": 138,
        "BPXSY2": 136,
        "BPXSY3": 134,
        "BPXDI1": 84,
        "BPXDI2": 82,
        "BPXDI3": 80,
        "BPQ020": 2,
        "BPQ150": 2,
    }])

    rows = build_hypertension_rows(merged, "2015-2016")

    assert len(rows) == 1
    assert rows[0]["nhanes_cycle"] == "2015-2016"


def test_build_hypertension_rows_harmonizes_2015_2016_medication_variable():
    import pandas as pd
    from src.build_cohorts_stage6 import build_hypertension_rows

    merged = pd.DataFrame([{
        "SEQN": 6001,
        "RIDAGEYR": 58,
        "BPXSY1": 146,
        "BPXSY2": 144,
        "BPXSY3": 142,
        "BPXDI1": 92,
        "BPXDI2": 90,
        "BPXDI3": 88,
        "BPQ020": 2,
        "BPQ050A": 1,
    }])

    rows = build_hypertension_rows(merged, "2015-2016")

    assert len(rows) == 1
    assert rows[0]["undiagnosed_hypertension"] == 0
