import pandas as pd


def test_clean_special_missing_codes_replaces_only_known_codes():
    from src.build_features_stage6 import clean_special_missing_codes

    series = pd.Series([1, 7, 9, 77, 99, 777, 999, 42, None])
    cleaned = clean_special_missing_codes(series)

    assert cleaned.iloc[0] == 1
    assert cleaned.iloc[7] == 42
    assert cleaned.isna().sum() == 7


def test_compute_bmi_valid_values():
    from src.build_features_stage6 import compute_bmi

    height = pd.Series([70, 60, 39, 84, None])
    weight = pd.Series([175, 120, 100, 200, 150])

    result = compute_bmi(height, weight)

    assert round(result.iloc[0], 2) == 25.11
    assert round(result.iloc[1], 2) == 23.43
    assert pd.isna(result.iloc[2])
    assert pd.isna(result.iloc[3])
    assert pd.isna(result.iloc[4])


def test_compute_phq9_total_requires_complete_valid_items():
    from src.build_features_stage6 import compute_phq9_total

    columns = [f"DPQ{number:03d}" for number in range(10, 100, 10)]

    df = pd.DataFrame(
        {
            column: [1, 0, 3]
            for column in columns
        }
    )
    df.loc[1, "DPQ050"] = None
    df.loc[2, "DPQ090"] = 7

    result = compute_phq9_total(df, columns)

    assert result.iloc[0] == 9
    assert pd.isna(result.iloc[1])
    assert pd.isna(result.iloc[2])


def test_merge_feature_source_is_left_join_and_preserves_rows():
    from src.build_features_stage6 import merge_feature_source

    cohort = pd.DataFrame(
        {
            "SEQN": [1, 2, 3],
            "nhanes_cycle": ["2011-2012"] * 3,
        }
    )
    feature_source = pd.DataFrame(
        {
            "SEQN": [1, 3],
            "SMQ020": [1, 2],
        }
    )

    merged = merge_feature_source(cohort, feature_source, ["SMQ020"])

    assert len(merged) == 3
    assert merged.loc[merged["SEQN"] == 2, "SMQ020"].isna().all()