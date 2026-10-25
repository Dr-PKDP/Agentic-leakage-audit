from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def main():
 p=argparse.ArgumentParser();p.add_argument("--raw",default="data/raw/development");p.add_argument("--output",default="data/metadata/development_schema_v2.csv");a=p.parse_args()
 rows=[]
 for f in sorted(Path(a.raw).rglob("*.XPT")):
  df=pd.read_sas(f,format="xport",encoding="latin1")
  for c in df.columns: rows.append({"cycle":f.parent.name,"file":f.name,"variable":c,"dtype":str(df[c].dtype),"nonmissing":int(df[c].notna().sum()),"rows":len(df)})
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(out,index=False);print(f"Wrote {out} with {len(rows)} variable records")
if __name__=="__main__":main()
