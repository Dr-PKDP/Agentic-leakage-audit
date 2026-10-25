import argparse,re,pandas as pd
p=argparse.ArgumentParser();p.add_argument("--ontology",required=True);p.add_argument("--task",required=True);p.add_argument("--features",required=True);a=p.parse_args();o=pd.read_csv(a.ontology);features=[x.strip().upper() for x in open(a.features) if x.strip()];rules=o[(o.task.eq(a.task))|(o.task.eq("ALL"))];bad=[f for f in features if any(re.match(r.pattern,f) for r in rules.itertuples())]
if bad: raise SystemExit("Forbidden/analysis-only features: "+", ".join(bad))
print("Ontology validation passed")
