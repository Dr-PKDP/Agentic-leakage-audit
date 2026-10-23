import argparse
from pathlib import Path
import pandas as pd
import requests
p=argparse.ArgumentParser()
p.add_argument("--manifest",required=True)
p.add_argument("--split",required=True)
p.add_argument("--output",required=True)
a=p.parse_args()
out=Path(a.output)
out.mkdir(parents=True,exist_ok=True)
for r in pd.read_csv(a.manifest).query("split == @a.split").itertuples():
    q=requests.get(r.url,timeout=120)
    q.raise_for_status()
    (out/(r.file+".xpt")).write_bytes(q.content)
