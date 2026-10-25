import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
from validate_survey_spec_stage4e import validate
def test_valid_spec():assert validate(Path(__file__).parents[1]/"protocol"/"P6_STAGE4E_SURVEY_RULES_v1.json")
