from pathlib import Path

import yaml


def test_stage7_protocol_has_untouched_temporal_test_cycle():
    path = Path("configs/stage7_hypertension_modeling_protocol.yaml")
    protocol = yaml.safe_load(path.read_text(encoding="utf-8"))

    development = set(protocol["temporal_split"]["development_cycles"])
    final_test = protocol["temporal_split"]["final_test_cycle"]

    assert final_test == "2021-2023"
    assert final_test not in development
    assert development == {"2011-2012", "2013-2014", "2015-2016"}


def test_stage7_protocol_excludes_target_and_survey_fields_from_predictors():
    path = Path("configs/stage7_hypertension_modeling_protocol.yaml")
    protocol = yaml.safe_load(path.read_text(encoding="utf-8"))

    excluded = set(protocol["target_exclusions"])

    assert protocol["target"] in excluded
    assert protocol["survey_design"]["weight"] in excluded
    assert protocol["survey_design"]["strata"] in excluded
    assert protocol["survey_design"]["psu"] in excluded