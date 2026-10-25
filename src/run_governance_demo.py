import argparse,json
from governance import evaluate_proposal
p=argparse.ArgumentParser();p.add_argument("--task",required=True);p.add_argument("--features",required=True,nargs="+");p.add_argument("--ontology",default="protocol/feature_governance_v1.json");p.add_argument("--log",default="logs/agent_actions.jsonl");a=p.parse_args();r=evaluate_proposal(a.task,a.features,a.ontology,log_path=a.log);print(json.dumps(r,indent=2));raise SystemExit(0 if r["approved"] else 2)
