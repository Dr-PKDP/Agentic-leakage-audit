from __future__ import annotations


def egfr_2021_ckd_epi(
    serum_creatinine_mg_dl: float,
    age_years: float,
    sex: str,
) -> float:
    if serum_creatinine_mg_dl <= 0:
        raise ValueError("serum_creatinine_mg_dl must be positive")

    if age_years < 18:
        raise ValueError("2021 CKD-EPI is defined here for adults only")

    normalized_sex = sex.strip().lower()

    parameters = {
        "female": (0.7, -0.241, 1.012),
        "male": (0.9, -0.302, 1.0),
    }

    if normalized_sex not in parameters:
        raise ValueError("sex must be 'female' or 'male'")

    kappa, alpha, sex_multiplier = parameters[normalized_sex]
    ratio = serum_creatinine_mg_dl / kappa

    return (
        142
        * min(ratio, 1.0) ** alpha
        * max(ratio, 1.0) ** -1.200
        * 0.9938 ** age_years
        * sex_multiplier
    )


def mean_valid_bp(
    readings: list[float | int | None],
    *,
    allow_zero: bool,
) -> float | None:
    import math

    valid_readings = []

    for reading in readings:
        if reading is None:
            continue

        value = float(reading)

        if not math.isfinite(value):
            continue

        if value < 0:
            continue

        if value == 0 and not allow_zero:
            continue

        valid_readings.append(value)

    if not valid_readings:
        return None

    return sum(valid_readings) / len(valid_readings)


def has_elevated_bp(
    mean_systolic: float | None,
    mean_diastolic: float | None,
) -> bool | None:
    if mean_systolic is None or mean_diastolic is None:
        return None

    return mean_systolic >= 130.0 or mean_diastolic >= 80.0


def normalize_nhanes_yes_no(value: object) -> bool | None:
    if value is None:
        return None

    try:
        code = int(float(value))
    except (TypeError, ValueError):
        return None

    if code == 1:
        return True

    if code == 2:
        return False

    return None


def undiagnosed_hypertension_label(
    elevated_bp: bool | None,
    known_hypertension: bool | None,
    taking_hypertension_medication: bool | None,
) -> int | None:
    if elevated_bp is None:
        return None

    if known_hypertension is None:
        return None

    if taking_hypertension_medication is None:
        return None

    if elevated_bp and not known_hypertension and not taking_hypertension_medication:
        return 1

    return 0


def _nhanes_bp_mean(readings: list[float | int | None], *, allow_zero: bool) -> float | None:
    preferred = mean_valid_bp(readings[1:3], allow_zero=allow_zero)
    if preferred is not None:
        return preferred
    return mean_valid_bp(readings, allow_zero=allow_zero)


def build_hypertension_row(source: dict[str, object]) -> dict[str, object]:
    mean_systolic = _nhanes_bp_mean(
        [
            source.get("BPXSY1"),
            source.get("BPXSY2"),
            source.get("BPXSY3"),
        ],
        allow_zero=False,
    )

    mean_diastolic = _nhanes_bp_mean(
        [
            source.get("BPXDI1"),
            source.get("BPXDI2"),
            source.get("BPXDI3"),
        ],
        allow_zero=True,
    )

    elevated_bp = has_elevated_bp(mean_systolic, mean_diastolic)
    known_hypertension = normalize_nhanes_yes_no(source.get("BPQ020"))

    medication_value = (
        source.get("BPQ150")
        if source.get("BPQ150") is not None
        else source.get("BPQ040A")
    )
    taking_medication = normalize_nhanes_yes_no(medication_value)

    label = undiagnosed_hypertension_label(
        elevated_bp,
        known_hypertension,
        taking_medication,
    )

    if elevated_bp is None:
        missing_reason = "missing_bp_measurement"
    elif known_hypertension is None:
        missing_reason = "unknown_hypertension_awareness"
    elif taking_medication is None:
        missing_reason = "unknown_hypertension_medication"
    else:
        missing_reason = None

    return {
        "SEQN": source.get("SEQN"),
        "RIDAGEYR": source.get("RIDAGEYR"),
        "RIAGENDR": source.get("RIAGENDR"),
        "WTMEC2YR": source.get("WTMEC2YR"),
        "SDMVPSU": source.get("SDMVPSU"),
        "SDMVSTRA": source.get("SDMVSTRA"),
        "mean_systolic_bp": mean_systolic,
        "mean_diastolic_bp": mean_diastolic,
        "elevated_bp_130_80": elevated_bp,
        "known_hypertension": known_hypertension,
        "taking_hypertension_medication": taking_medication,
        "undiagnosed_hypertension": label,
        "outcome_missing_reason": missing_reason,
    }

from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]

HYPERTENSION_SOURCE_FILES = {
    "2011-2012": {
        "demo": REPO_ROOT / "data" / "raw" / "nhanes" / "DEMO_G.XPT",
        "bpx": REPO_ROOT / "data" / "raw" / "nhanes" / "BPX_G.XPT",
        "bpq": REPO_ROOT / "data" / "raw" / "nhanes" / "BPQ_G.XPT",
    },
    "2013-2014": {
        "demo": REPO_ROOT / "data" / "raw" / "nhanes" / "DEMO_H.XPT",
        "bpx": REPO_ROOT / "data" / "raw" / "nhanes" / "BPX_H.XPT",
        "bpq": REPO_ROOT / "data" / "raw" / "nhanes" / "BPQ_H.XPT",
    },
    "2015-2016": {
        "demo": REPO_ROOT / "data" / "raw" / "nhanes" / "DEMO_I.XPT",
        "bpx": REPO_ROOT / "data" / "raw" / "nhanes" / "BPX_I.XPT",
        "bpq": REPO_ROOT / "data" / "raw" / "nhanes" / "BPQ_I.XPT",
    },
    "2021-2023": {
        "demo": REPO_ROOT / "data" / "raw" / "nhanes" / "DEMO_L.XPT",
        "bpx": REPO_ROOT / "data" / "raw" / "nhanes" / "BPXO_L.XPT",
        "bpq": REPO_ROOT / "data" / "raw" / "nhanes" / "BPQ_L.XPT",
    },
}


HYPERTENSION_CYCLE_SPECS = {
    "2011-2012": {
        "systolic_columns": ["BPXSY1", "BPXSY2", "BPXSY3"],
        "diastolic_columns": ["BPXDI1", "BPXDI2", "BPXDI3"],
        "medication_column": "BPQ050A",
    },
    "2013-2014": {
        "systolic_columns": ["BPXSY1", "BPXSY2", "BPXSY3"],
        "diastolic_columns": ["BPXDI1", "BPXDI2", "BPXDI3"],
        "medication_column": "BPQ050A",
    },
    "2015-2016": {
        "systolic_columns": ["BPXSY1", "BPXSY2", "BPXSY3"],
        "diastolic_columns": ["BPXDI1", "BPXDI2", "BPXDI3"],
        "medication_column": "BPQ050A",
    },
    "2021-2023": {
        "systolic_columns": ["BPXOSY1", "BPXOSY2", "BPXOSY3"],
        "diastolic_columns": ["BPXODI1", "BPXODI2", "BPXODI3"],
        "medication_column": "BPQ150",
    },
}


def merge_hypertension_components(
    demographics: pd.DataFrame,
    blood_pressure: pd.DataFrame,
    questionnaire: pd.DataFrame,
) -> pd.DataFrame:
    for frame_name, frame in {
        "demographics": demographics,
        "blood_pressure": blood_pressure,
        "questionnaire": questionnaire,
    }.items():
        if "SEQN" not in frame.columns:
            raise KeyError(f"{frame_name} is missing SEQN")

        if frame["SEQN"].duplicated().any():
            raise ValueError(f"{frame_name} contains duplicate SEQN values")

    merged = demographics.merge(
        blood_pressure,
        on="SEQN",
        how="inner",
        validate="one_to_one",
    )
    merged = merged.merge(
        questionnaire,
        on="SEQN",
        how="left",
        validate="one_to_one",
    )
    return merged


def load_hypertension_cycle(cycle: str) -> pd.DataFrame:
    if cycle not in HYPERTENSION_SOURCE_FILES:
        raise ValueError(f"Unsupported NHANES cycle: {cycle}")

    paths = HYPERTENSION_SOURCE_FILES[cycle]
    missing = [str(path) for path in paths.values() if not path.exists()]

    if missing:
        raise FileNotFoundError(
            f"Missing validated NHANES source files for {cycle}: {missing}"
        )

    demographics = pd.read_sas(paths["demo"], format="xport")
    blood_pressure = pd.read_sas(paths["bpx"], format="xport")
    questionnaire = pd.read_sas(paths["bpq"], format="xport")

    merged = merge_hypertension_components(
        demographics,
        blood_pressure,
        questionnaire,
    )
    merged["nhanes_cycle"] = cycle
    return merged


def _to_python_scalar(value):
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def build_hypertension_rows(
    merged: pd.DataFrame,
    cycle: str,
) -> list[dict[str, object]]:
    if cycle not in HYPERTENSION_CYCLE_SPECS:
        raise ValueError(f"Unsupported NHANES cycle: {cycle}")

    spec = HYPERTENSION_CYCLE_SPECS[cycle]
    medication_column = spec["medication_column"]

    rows = []

    for _, row in merged.iterrows():
        source = {column: _to_python_scalar(value) for column, value in row.items()}

        source["BPXSY1"] = source.get(spec["systolic_columns"][0])
        source["BPXSY2"] = source.get(spec["systolic_columns"][1])
        source["BPXSY3"] = source.get(spec["systolic_columns"][2])

        source["BPXDI1"] = source.get(spec["diastolic_columns"][0])
        source["BPXDI2"] = source.get(spec["diastolic_columns"][1])
        source["BPXDI3"] = source.get(spec["diastolic_columns"][2])

        source["BPQ150"] = source.get(medication_column)

        output_row = build_hypertension_row(source)

        # NHANES skips the medication item after a "No" awareness response.
        # In this defined cohort, skipped medication then means no BP medicine.
        if (
            output_row["known_hypertension"] is False
            and output_row["taking_hypertension_medication"] is None
        ):
            output_row["taking_hypertension_medication"] = False
            output_row["undiagnosed_hypertension"] = undiagnosed_hypertension_label(
                output_row["elevated_bp_130_80"],
                output_row["known_hypertension"],
                output_row["taking_hypertension_medication"],
            )
            output_row["outcome_missing_reason"] = (
                "missing_bp_measurement"
                if output_row["elevated_bp_130_80"] is None
                else None
            )

        output_row["nhanes_cycle"] = cycle
        rows.append(output_row)

    return rows

from datetime import datetime


def build_stage6_hypertension_cohort(
    cycles: list[str] | None = None,
) -> pd.DataFrame:
    if cycles is None:
        cycles = ["2011-2012", "2013-2014", "2015-2016", "2021-2023"]

    all_rows: list[dict[str, object]] = []

    for cycle in cycles:
        merged = load_hypertension_cycle(cycle)
        rows = build_hypertension_rows(merged, cycle)
        all_rows.extend(rows)

    cohort = pd.DataFrame(all_rows)

    expected_columns = [
        "SEQN",
        "RIDAGEYR",
        "RIAGENDR",
        "WTMEC2YR",
        "SDMVPSU",
        "SDMVSTRA",
        "mean_systolic_bp",
        "mean_diastolic_bp",
        "elevated_bp_130_80",
        "known_hypertension",
        "taking_hypertension_medication",
        "undiagnosed_hypertension",
        "outcome_missing_reason",
        "nhanes_cycle",
    ]

    for col in expected_columns:
        if col not in cohort.columns:
            cohort[col] = None

    cohort = cohort[expected_columns]
    return cohort


def write_stage6_hypertension_cohort(
    output_path: str | Path | None = None,
    cycles: list[str] | None = None,
) -> Path:
    if output_path is None:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output_path = (
            REPO_ROOT
            / "outputs"
            / "cohorts"
            / f"P6_STAGE6_hypertension_cohort_{timestamp}.csv"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cohort = build_stage6_hypertension_cohort(cycles=cycles)
    cohort.to_csv(output_path, index=False)

    return output_path


def main() -> None:
    output_path = write_stage6_hypertension_cohort()
    print(output_path)


if __name__ == "__main__":
    main()