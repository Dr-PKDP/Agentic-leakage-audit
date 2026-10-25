from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import requests

FILES=("DEMO","GHB","GLU","DIQ","BPX","DPQ")
CYCLES={"2011-2012":("2011","G"),"2013-2014":("2013","H"),"2015-2016":("2015","I")}
def download(url,dest):
    r=requests.get(url,timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"HEADER RECORD"):
        raise RuntimeError(f"Expected NHANES XPT; received non-XPT content from {url}")
    dest.write_bytes(r.content)
    return {"url":url,"bytes":len(r.content),"sha256":hashlib.sha256(r.content).hexdigest()}
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",default="data/raw/development");a=p.parse_args()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True); manifest=[]
    for cycle,(year,suffix) in CYCLES.items():
        folder=out/cycle;folder.mkdir(exist_ok=True)
        for code in FILES:
            name=f"{code}_{suffix}.XPT"; url=f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}"
            entry={"cycle":cycle,"file":name};entry.update(download(url,folder/name));manifest.append(entry);print(f"Downloaded {cycle}/{name}: {entry['bytes']} bytes")
    Path("logs").mkdir(exist_ok=True);Path("logs/acquisition_manifest.json").write_text(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
