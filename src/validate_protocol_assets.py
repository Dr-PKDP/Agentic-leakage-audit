import json
from pathlib import Path
REQUIRED={"medication_exclusion_spec_v1.json":["version","unit_of_analysis","quality_gates"],"ckd_biomarker_spec_v1.json":["outcome_name","required_sources","quality_gates"],"cohort_flow_spec_v1.json":["columns","required_stages","rules"],"feature_governance_extension_stage4b_v1.json":["rules"]}
def validate(protocol_dir):
 for name,keys in REQUIRED.items():
  data=json.loads((Path(protocol_dir)/name).read_text())
  missing=[k for k in keys if k not in data]
  if missing: raise ValueError(f"{name} missing {missing}")
 return True
if __name__=="__main__":
 validate("protocol");print("Stage 4B protocol assets validated")
