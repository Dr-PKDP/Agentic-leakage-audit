from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "nhanes"
COHORT_PATH = (
    REPO_ROOT
    / "outputs"
    / "cohorts"
    / "P6_STAGE6_hypertension_cohort_20261023T163306Z.csv"
)
SPEC_PATH = REPO_ROOT / "configs" / "stage6_hypertension_feature_spec.yaml"
OUTPUT_DIR = REPO_ROOT / "outputs" / "features"

CYCLE_SUFFIX = {
    "2011-2012": "G",
    "2013-2014": "H",
    "2015-2016": "I",
    "2021-2023": "L",
}

SOURCE_FOR_VARIABLE = {
    "ALQ": "ALQ",
    "DIQ": "DIQ",
    "DPQ": "DPQ",
    "MCQ": "MCQ",
    "PAD": "PAQ",
    "SMA": "SMQ",
    "SMD": "SMQ",
    "SMQ": "SMQ",
    "WHD": "WHQ",
    "WHQ": "WHQ",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = [
        column.decode("utf-8") if isinstance(column, bytes) else str(column)
        for column in result.columns
    ]
    return result


def read_xpt(path: Path) -> pd.DataFrame:
    return normalize_columns(pd.read_sas(path, format="xport"))


def clean_special_missing_codes(series: pd.Series) -> pd.Series:
    return series.replace([7, 9, 77, 99, 777, 999, 7777, 9999], pd.NA)


def compute_bmi(height_inches: pd.Series, weight_pounds: pd.Series) -> pd.Series:
    height = pd.to_numeric(height_inches, errors="coerce")
    weight = pd.to_numeric(weight_pounds, errors="coerce")

    valid = (
        height.between(40, 83)
        & weight.between(63, 530)
    )
    bmi = 703 * weight / (height**2)
    return bmi.where(valid)


def compute_phq9_total(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    values = df[columns].apply(pd.to_numeric, errors="coerce")
    valid_values = values.apply(lambda series: series.between(0, 3))
    complete_valid = valid_values.all(axis=1)
    return values.sum(axis=1).where(complete_valid)


def merge_feature_source(
    cohort: pd.DataFrame,
    feature_source: pd.DataFrame,
    variables: list[str],
) -> pd.DataFrame:
    variables_to_add = [
        variable
        for variable in variables
        if variable in feature_source.columns and variable not in cohort.columns
    ]

    if not variables_to_add:
        return cohort

    selected = ["SEQN"] + variables_to_add
    source = feature_source[selected].drop_duplicates("SEQN")

    return cohort.merge(
        source,
        on="SEQN",
        how="left",
        validate="one_to_one",
    )


def source_for_variable(variable: str) -> str:
    if variable.startswith(("RID", "RIA", "DMD", "DMQ", "IND", "WT", "SDD", "SDM")):
        return "DEMO"

    for prefix, source in SOURCE_FOR_VARIABLE.items():
        if variable.startswith(prefix):
            return source

    raise ValueError(f"No feature source mapping for variable: {variable}")


def load_spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def collect_base_variables(spec: dict) -> list[str]:
    primary = spec["primary_minimal_screening"]

    variables = (
        primary["demographics"]
        + primary["alcohol"]
        + primary["smoking"]
        + primary["physical_activity"]
        + primary["weight_history"]
        + primary["depression"]["items"]
    )

    expanded = spec["expanded_health_history"]
    variables += expanded["diabetes_history"]
    variables += expanded["medical_conditions"]

    return list(dict.fromkeys(variables))


def build_cycle_features(
    cohort_cycle: pd.DataFrame,
    cycle: str,
    spec: dict,
) -> pd.DataFrame:
    suffix = CYCLE_SUFFIX[cycle]
    variables = collect_base_variables(spec)

    result = cohort_cycle.copy()

    grouped: dict[str, list[str]] = {}
    for variable in variables:
        grouped.setdefault(source_for_variable(variable), []).append(variable)

    for source, source_variables in grouped.items():
        path = RAW_DIR / f"{source}_{suffix}.XPT"
        source_df = read_xpt(path)
        result = merge_feature_source(result, source_df, source_variables)

        missing_codes = spec["response_handling"]["numeric_missing_codes"]

    for variable in variables:
        if variable in result.columns:
            result[variable] = result[variable].replace(missing_codes, pd.NA)

    phq_items = spec["primary_minimal_screening"]["depression"]["items"]
    phq9_total = compute_phq9_total(result, phq_items)
    self_reported_bmi = compute_bmi(result["WHD010"], result["WHD020"])

    indicator_columns = {
        f"{variable}__missing": result[variable].isna().astype("int8")
        for variable in variables
        if variable in result.columns
    }
    indicator_columns["phq9_total__missing"] = phq9_total.isna().astype("int8")
    indicator_columns["self_reported_bmi__missing"] = (
        self_reported_bmi.isna().astype("int8")
    )

    derived_columns = pd.DataFrame(
        {
            "phq9_total": phq9_total,
            "self_reported_bmi": self_reported_bmi,
            **indicator_columns,
        },
        index=result.index,
    )

    return pd.concat([result, derived_columns], axis=1).copy()
    

def make_feature_sets(feature_table: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    primary = spec["primary_minimal_screening"]

    minimal_features = (
    primary["demographics"]
    + primary["alcohol"]
    + primary["smoking"]
    + primary["physical_activity"]
    + primary["weight_history"]
    + primary["depression"]["items"]
    + ["phq9_total", "self_reported_bmi"]
)

    expanded_features = (
        minimal_features
        + spec["expanded_health_history"]["diabetes_history"]
        + spec["expanded_health_history"]["medical_conditions"]
    )

    base_columns = [
        "SEQN",
        "nhanes_cycle",
        "undiagnosed_hypertension",
        "WTMEC2YR",
        "SDMVSTRA",
        "SDMVPSU",
    ]

    def with_missing_indicators(columns: list[str]) -> list[str]:
        indicators = [
            f"{column}__missing"
            for column in columns
            if f"{column}__missing" in feature_table.columns
        ]
        return list(dict.fromkeys(base_columns + columns + indicators))

    return (
        feature_table[with_missing_indicators(minimal_features)].copy(),
        feature_table[with_missing_indicators(expanded_features)].copy(),
    )


def main() -> None:
    spec = load_spec()

    if not COHORT_PATH.exists():
        raise FileNotFoundError(f"Missing cohort artifact: {COHORT_PATH}")

    cohort = pd.read_csv(COHORT_PATH)
    cohort = cohort.loc[cohort["undiagnosed_hypertension"].notna()].copy()

    cycle_tables = []
    for cycle, cohort_cycle in cohort.groupby("nhanes_cycle", sort=True):
        cycle_tables.append(build_cycle_features(cohort_cycle, cycle, spec))

    feature_table = pd.concat(cycle_tables, ignore_index=True)
    minimal, expanded = make_feature_sets(feature_table, spec)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_path = OUTPUT_DIR / "P6_STAGE6_hypertension_features_all.csv"
    minimal_path = OUTPUT_DIR / "P6_STAGE6_hypertension_features_minimal.csv"
    expanded_path = OUTPUT_DIR / "P6_STAGE6_hypertension_features_expanded.csv"
    audit_path = OUTPUT_DIR / "P6_STAGE6_hypertension_features_audit.csv"

    feature_table.to_csv(all_path, index=False)
    minimal.to_csv(minimal_path, index=False)
    expanded.to_csv(expanded_path, index=False)

    audit = pd.DataFrame(
        {
            "column": feature_table.columns,
            "missing_fraction": feature_table.isna().mean().round(6).values,
            "unique_nonmissing": [
                feature_table[column].nunique(dropna=True)
                for column in feature_table.columns
            ],
        }
    )
    audit.to_csv(audit_path, index=False)

    print(all_path)
    print(minimal_path)
    print(expanded_path)
    print(audit_path)
    print(f"Rows: {len(feature_table)}")


if __name__ == "__main__":
    main()