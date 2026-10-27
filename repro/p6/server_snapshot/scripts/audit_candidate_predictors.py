import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pyreadstat

root = Path(os.environ["P6_DIR"])
config = json.loads(
    (root / "configs/nhanes_depression_dev_v1.json").read_text()
)
raw = root / "data/raw/nhanes/2017_2018"

demo, _ = pyreadstat.read_xport(str(raw / "DEMO_J.xpt"))
dpq, _ = pyreadstat.read_xport(str(raw / "DPQ_J.xpt"))

for name, table in (("DEMO_J", demo), ("DPQ_J", dpq)):
    if table["SEQN"].isna().any() or table["SEQN"].duplicated().any():
        raise SystemExit(f"STOP: invalid identifiers in {name}.")

columns = [
    "SEQN", "RIDAGEYR", "RIAGENDR", "INDFMPIR",
    "WTMEC2YR", "SDMVSTRA", "SDMVPSU"
]
joined = dpq.merge(
    demo[columns],
    on="SEQN",
    how="left",
    validate="one_to_one",
    indicator=True
)
if not joined["_merge"].eq("both").all():
    raise SystemExit("STOP: unmatched identifiers.")

items = config["outcome"]["items"]
valid_items = joined[items].isin(
    config["outcome"]["valid_item_values"]
).all(axis=1)

eligible = joined["RIDAGEYR"].ge(
    config["population"]["minimum_age"]
)
if config["population"]["require_positive_mec_weight"]:
    eligible &= joined["WTMEC2YR"].gt(0)
if config["population"]["require_design_fields_present"]:
    eligible &= joined[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)

cohort = joined.loc[eligible & valid_items].copy()

age = cohort["RIDAGEYR"]
gender = cohort["RIAGENDR"]
income = cohort["INDFMPIR"]

checks = {
    "age_present_integer_and_in_18_to_80": bool(
        age.notna().all()
        and age.between(18, 80).all()
        and age.mod(1).eq(0).all()
    ),
    "gender_present_and_in_1_2": bool(
        gender.notna().all() and gender.isin([1, 2]).all()
    ),
    "nonmissing_income_in_0_to_5": bool(
        income.dropna().between(0, 5).all()
    )
}

report = {
    "purpose": "candidate-predictor development audit",
    "outcome_eligible_records": int(len(cohort)),
    "proposed_predictors": ["RIDAGEYR", "RIAGENDR", "INDFMPIR"],
    "age": {
        "missing": int(age.isna().sum()),
        "age_18_or_19": int(age.isin([18, 19]).sum()),
        "topcoded_80_plus": int(age.eq(80).sum())
    },
    "released_gender_counts": {
        "male_code_1": int(gender.eq(1).sum()),
        "female_code_2": int(gender.eq(2).sum()),
        "missing": int(gender.isna().sum())
    },
    "income_to_poverty_ratio": {
        "missing": int(income.isna().sum()),
        "observed": int(income.notna().sum()),
        "topcoded_at_5": int(income.eq(5).sum()),
        "minimum": float(income.min()) if income.notna().any() else None,
        "maximum": float(income.max()) if income.notna().any() else None
    },
    "checks": checks,
    "no_predictor_imputation_performed": True,
    "no_model_training_performed": True,
    "no_participant_level_output_saved": True
}

out = root / "outputs/data_inspection"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
path = out / f"candidate_predictors_{stamp}.json"
with path.open("x") as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write("\n")

print(json.dumps(report, indent=2, allow_nan=False))
print("\nSaved:", path)
