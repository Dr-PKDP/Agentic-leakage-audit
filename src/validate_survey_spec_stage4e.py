import json
from pathlib import Path
REQUIRED=["version","cycles","design_variables","pooled_weight_rule","prohibitions","required_outputs","status"]
def validate(path):
 d=json.loads(Path(path).read_text());missing=[k for k in REQUIRED if k not in d]
 if missing:raise ValueError("Missing keys: "+", ".join(missing))
 if d["design_variables"]["strata"]!="SDMVSTRA" or d["design_variables"]["psu"]!="SDMVPSU":raise ValueError("Incorrect design variables")
 if "divide" not in d["pooled_weight_rule"].lower():raise ValueError("Pooled-weight rule absent")
 return True
if __name__=="__main__":validate("protocol/P6_STAGE4E_SURVEY_RULES_v1.json");print("Stage 4E survey specification validated")
