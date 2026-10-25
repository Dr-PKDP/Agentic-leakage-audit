from __future__ import annotations
import json,uuid
from datetime import datetime,timezone
from pathlib import Path

def load_ontology(path):
    return json.loads(Path(path).read_text())
def classify(task,feature,ontology):
    taskdef=ontology["tasks"][task]; f=feature.upper()
    if f in taskdef["analysis_only"]: return "analysis_only","Identifier or survey-design field; not a predictor."
    if f in taskdef["outcome_inputs"]: return "blocked","Direct outcome-construction input."
    if any(f.startswith(p) for p in taskdef["forbidden_prefixes"]): return "blocked","Task-specific outcome, diagnosis, treatment, or proxy prefix."
    return "allowed","No rule matched; requires codebook-auditor review before modeling."
def evaluate_proposal(task,features,ontology_path,agent_role="modeller",partition="development",log_path=None):
    o=load_ontology(ontology_path)
    if partition in o["split_contract"]["locked_test_cycles"]: raise ValueError("Locked test partition cannot be used for proposal evaluation.")
    decisions=[]
    for feature in features:
        decision,reason=classify(task,feature,o);decisions.append({"feature":feature,"decision":decision,"reason":reason})
    record={"run_id":str(uuid.uuid4()),"proposal_id":str(uuid.uuid4()),"task":task,"agent_role":agent_role,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"ontology_version":o["version"],"data_partition":partition,"decisions":decisions,"approved":all(d["decision"]=="allowed" for d in decisions)}
    if log_path:
        Path(log_path).parent.mkdir(parents=True,exist_ok=True)
        with open(log_path,"a",encoding="utf-8") as f:f.write(json.dumps(record)+"\n")
    return record
