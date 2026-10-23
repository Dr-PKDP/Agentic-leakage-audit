import argparse
from pathlib import Path
import pandas as pd
p=argparse.ArgumentParser();p.add_argument("--schema",required=True);p.add_argument("--output",required=True);a=p.parse_args()
s=pd.read_csv(a.schema);s["component"]=s.file.str.replace(r"_[A-Z]$","",regex=True)
h=s.groupby(["component","variable"],as_index=False).agg(cycles=("cycle",lambda x:"|".join(sorted(set(x)))),n_cycles=("cycle","nunique"),dtypes=("dtype",lambda x:"|".join(sorted(set(x)))))
Path(a.output).parent.mkdir(parents=True,exist_ok=True);h.to_csv(a.output,index=False)
