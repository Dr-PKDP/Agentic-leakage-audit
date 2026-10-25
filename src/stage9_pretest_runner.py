from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from src.stage9_execution_gate import check_execution_gate


REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_PATH = (
    REPO_ROOT
    / "outputs"
    / "features"
    / "P6_STAGE6_hypertension_features_minimal.csv"
)
RUN_DIR = REPO_ROOT / "outputs" / "stage9_runs"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_data(
    df: pd.DataFrame,
    proposal: dict,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame, pd.DataFrame]:
    predictors = proposal["predictors"]
    target = proposal["target"]
    train_cycles = proposal["training_cycles"]
    test_cycle = proposal["evaluation_cycle"]

    train = df.loc[df["nhanes_cycle"].isin(train_cycles)].copy()
    test = df.loc[df["nhanes_cycle"].eq(test_cycle)].copy()

    required = predictors + [target, "WTMEC2YR", "SEQN", "nhanes_cycle"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Feature table missing required columns: {missing}")

    if train.empty:
        raise ValueError("No rows found for declared training cycles.")

    if test.empty:
        raise ValueError("No rows found for declared evaluation cycle.")

    X_train = train[predictors].copy()
    y_train = train[target].copy()
    w_train = train["WTMEC2YR"].copy()

    # Construct locked-test features without selecting its target column.
    X_test = test[predictors].copy()
    test_ids = test[["SEQN", "nhanes_cycle"]].copy()

    return X_train, y_train, w_train, X_test, test_ids


def make_model(proposal: dict) -> RandomForestClassifier:
    settings = proposal["model"]

    if settings["name"] != "random_forest":
        raise ValueError(
            f"Unsupported model: {settings['name']}. "
            "Only random_forest is enabled in this pre-test runner."
        )

    return RandomForestClassifier(
        n_estimators=settings.get("n_estimators", 500),
        min_samples_leaf=settings.get("min_samples_leaf", 10),
        class_weight=settings.get("class_weight", "balanced"),
        random_state=settings["random_state"],
        n_jobs=-1,
    )


def make_prediction_frame(
    test_ids: pd.DataFrame,
    prediction: pd.Series | list | object,
) -> pd.DataFrame:
    result = test_ids.copy()
    result["predicted_risk"] = prediction
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_id = args.run_id
    manifest_path = RUN_DIR / f"{run_id}_manifest.json"
    proposal_record_path = RUN_DIR / f"{run_id}_proposal_record.json"
    output_path = RUN_DIR / f"{run_id}_locked_test_predictions.csv"

    manifest = load_json(manifest_path)
    proposal_record = load_json(proposal_record_path)

    gate = check_execution_gate(manifest, proposal_record)
    if gate["status"] != "pass":
        raise PermissionError(
            f"Pre-test execution blocked: {gate['details']}"
        )

    proposal = proposal_record["proposal"]
    df = pd.read_csv(FEATURE_PATH)

    X_train, y_train, w_train, X_test, test_ids = prepare_data(
        df,
        proposal,
    )

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", make_model(proposal)),
        ]
    )
    pipeline.fit(
        X_train,
        y_train,
        model__sample_weight=w_train,
    )

    prediction = pipeline.predict_proba(X_test)[:, 1]
    prediction_frame = make_prediction_frame(test_ids, prediction)
    prediction_frame.to_csv(output_path, index=False)

    run_record = {
        "run_id": run_id,
        "stage": "pretest_prediction",
        "gate": gate,
        "training_rows": len(X_train),
        "locked_test_rows": len(X_test),
        "predictor_count": len(proposal["predictors"]),
        "prediction_path": str(output_path.relative_to(REPO_ROOT)),
        "target_column_read_from_test": False,
    }

    record_path = RUN_DIR / f"{run_id}_pretest_run_record.json"
    record_path.write_text(
        json.dumps(run_record, indent=2),
        encoding="utf-8",
    )

    print(record_path)
    print(json.dumps(run_record, indent=2))


if __name__ == "__main__":
    main()