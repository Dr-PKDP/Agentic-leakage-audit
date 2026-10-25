import json,sys,tempfile
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
from audit_source_completeness import audit
def test_missing_files_are_reported():
 with tempfile.TemporaryDirectory() as d:
  schema=Path(__file__).parents[1]/"protocol"/"P6_STAGE4C_AUDIT_SCHEMA_v1.json"
  out=audit(d,schema)
  assert len(out)==27
  assert set(out.status)=={"missing_file"}
def test_schema_has_nine_modules():
 s=json.loads((Path(__file__).parents[1]/"protocol"/"P6_STAGE4C_AUDIT_SCHEMA_v1.json").read_text())
 assert len(s["required_module_codes"])==9
