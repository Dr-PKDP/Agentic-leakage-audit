import argparse, hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(1048576),b""): h.update(part)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True); p.add_argument("--split",required=True)
    p.add_argument("--output",required=True); p.add_argument("--log",required=True); p.add_argument("--inventory",required=True)
    a=p.parse_args()
    if a.split.startswith("locked"): raise SystemExit("Locked split refused by acquisition script.")
    m=pd.read_csv(a.manifest); sub=m[m["split"]==a.split]
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True); records=[]
    for r in sub.itertuples(index=False):
        dest=out/(r.file+".xpt")
        event={"timestamp_utc":datetime.now(timezone.utc).isoformat(),"cycle":r.cycle,"split":r.split,"file":r.file,"url":r.url}
        if dest.exists() and dest.stat().st_size>1024:
            event.update(status="reused",bytes=dest.stat().st_size,sha256=digest(dest))
        else:
            try:
                q=requests.get(r.url,timeout=(20,180)); q.raise_for_status(); dest.write_bytes(q.content)
                event.update(status="downloaded",http_status=q.status_code,bytes=dest.stat().st_size,sha256=digest(dest))
            except Exception as e: event.update(status="failed",error=repr(e),bytes=None,sha256=None)
        with Path(a.log).open("a",encoding="utf-8") as h:h.write(json.dumps(event,sort_keys=True)+"\n")
        records.append(event)
    pd.DataFrame(records).to_csv(a.inventory,index=False)
    if any(x["status"]=="failed" for x in records):raise SystemExit(2)
if __name__=="__main__":main()
