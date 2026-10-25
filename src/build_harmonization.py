from pathlib import Path
import json
raw=Path("data/raw/development")
files=list(raw.rglob("*.XPT"))
if len(files)!=18: raise SystemExit(f"Expected 18 downloaded XPT files; found {len(files)}")
Path("data/metadata").mkdir(parents=True,exist_ok=True)
Path("data/metadata/harmonization_v1.json").write_text(json.dumps({"cycles":["2011-2012","2013-2014","2015-2016"],"files":len(files),"key":"SEQN"},indent=2))
print("Harmonization preflight passed")
