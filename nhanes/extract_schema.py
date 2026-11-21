import argparse
from pathlib import Path
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--inventory", required=True)
p.add_argument("--raw-dir", required=True)
p.add_argument("--output", required=True)
p.add_argument("--report", required=True)
a = p.parse_args()
inv = pd.read_csv(a.inventory)
schema = []
report = []
for r in inv[inv.status.isin(["downloaded", "reused"])].itertuples(index=False):
    try:
        d = pd.read_sas(Path(a.raw_dir) / (r.file + ".xpt"), format="xport", encoding="latin1")
        schema += [
            {"cycle": r.cycle, "split": r.split, "file": r.file, "variable": str(c), "dtype": str(d[c].dtype)}
            for c in d.columns
        ]
        report.append({"cycle": r.cycle, "file": r.file, "status": "parsed", "rows": len(d), "columns": len(d.columns)})
    except Exception as e:
        report.append({"cycle": r.cycle, "file": r.file, "status": "failed", "error": repr(e)})
Path(a.output).parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(schema).to_csv(a.output, index=False)
pd.DataFrame(report).to_csv(a.report, index=False)
