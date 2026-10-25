import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
from validate_protocol_assets import validate
P=Path(__file__).parents[1]/"protocol"
def test_assets_validate():assert validate(P)
def test_ckd_wording_guard():
 d=json.loads((P/"ckd_biomarker_spec_v1.json").read_text());assert d["prohibited_label"]=="confirmed chronic kidney disease"
def test_medication_unresolved_guard():
 d=json.loads((P/"medication_exclusion_spec_v1.json").read_text());assert "unresolved" in d["exclusions"]["T1_diabetes_screening"].lower()
def test_flow_has_reconciliation_stages():
 d=json.loads((P/"cohort_flow_spec_v1.json").read_text());assert "positive outcome" in d["required_stages"] and "negative outcome" in d["required_stages"]
