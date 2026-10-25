from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

def audit(raw_root,schema_path):
 spec=json.loads(Path(schema_path).read_text()); rows=[]
 for cycle,suffix in spec["development_cycles"].items():
  cdir=Path(raw_root)/cycle
  for code in spec["required_module_codes"]:
   file=cdir/f"{code}_{suffix}.XPT"
   row={"cycle":cycle,"module":code,"file":str(file),"status":"present","n_rows":None,"n_columns":None,"missing_required_columns":""}
   if not file.is_file(): row["status"]="missing_file";rows.append(row);continue
   try: df=pd.read_sas(file,format="xport",encoding="latin1")
   except Exception: row["status"]="unreadable";rows.append(row);continue
   row["n_rows"],row["n_columns"]=len(df),len(df.columns)
   required=spec["required_demo_columns"] if code=="DEMO" else []
   missing=[c for c in required if c not in df.columns]
   if missing:row["status"]="missing_columns";row["missing_required_columns"]=";".join(missing)
   rows.append(row)
 return pd.DataFrame(rows)
def task_column_audit(raw_root,schema_path):
 spec=json.loads(Path(schema_path).read_text()); rows=[]
 for task,columns in spec["minimum_task_columns"].items():
  for cycle,suffix in spec["development_cycles"].items():
   files=list((Path(raw_root)/cycle).glob(f"*_{suffix}.XPT"));allcols=set()
   for f in files:
    try:allcols.update(pd.read_sas(f,format="xport",encoding="latin1").columns)
    except Exception:pass
   missing=[c for c in columns if c not in allcols]
   rows.append({"task":task,"cycle":cycle,"status":"present" if not missing else "missing_columns","missing_columns":";".join(missing)})
 return pd.DataFrame(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument("--raw",default="data/raw/development");p.add_argument("--schema",default="protocol/P6_STAGE4C_AUDIT_SCHEMA_v1.json");p.add_argument("--output-dir",default="results/source_audit");a=p.parse_args();out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
 m=audit(a.raw,a.schema);t=task_column_audit(a.raw,a.schema);m.to_csv(out/"source_module_audit_v1.csv",index=False);t.to_csv(out/"task_column_audit_v1.csv",index=False);print(f"Wrote {len(m)} module checks and {len(t)} task checks to {out}");print(m.status.value_counts().to_dict());print(t.status.value_counts().to_dict())
if __name__=="__main__":main()
