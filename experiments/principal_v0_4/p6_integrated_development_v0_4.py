"""P6 v0.4 integrated synthetic development runner; generation requires explicit plan approval."""
import argparse, copy, hashlib, json, os, time, urllib.request
from pathlib import Path
T,F,U="supported","contradicted_contract","insufficient_evidence"
VERSION="p6_integrated_development_0.4"
STREAMS=("self_review","structure_feedback","evidence_critic","patch_critic")

def sha(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def write(path,x):
    with path.open("x",encoding="utf-8") as h:json.dump(x,h,indent=2);h.write("\n")
def same(a,b):return sha(a)==sha(b)

def contexts():
    bank=[]
    def add(family,arch,facts,good,bad,rule,uncertain=False):
        cid=f"P6D04_C{len(bank)+1:03d}"
        schema={k:{"type":"boolean" if type(v) is bool else "string_list" if isinstance(v,list) else "string","allow_empty":k=="selected"} for k,v in good.items()}
        public={"context_id":cid,"family":family,"archetype":arch,"scope_id":cid,"cutoff":10,
                "evidence":[{"evidence_id":cid+"/E01","scope_id":cid,"content":facts},{"evidence_id":"OTHER/"+cid+"/E02","scope_id":"OTHER","content":{"approved":True,"performed":True,"ready_time":1,"note":"This is evidence for another scope."}}],
                "rule_id":family+"/"+arch,"public_rule":rule,"proposal_schema":schema,
                "source_status":"SYNTHETIC_AUTHORED_DEVELOPMENT_NOT_HELDOUT",
                "dependence_unit":"UNRESOLVED_"+family}
        bank.append({"public":public,"valid_or_conservative":good,"counterpart":bad,"counterpart_expected":U if uncertain else F})
    fr="No selected feature may depend on a target component or target-observation record. Follow dependency paths. Missing provenance remains unresolved; empty selection may express deferral."
    add("F01","direct_ingredient",{"features":{"SAFE":{"deps":[]},"TARGET":{"target":True}},"target_records":[]},{"selected":["SAFE"]},{"selected":["SAFE","TARGET"]},fr)
    add("F01","transitive_dependency",{"features":{"SAFE":{"deps":[]},"DERIVED":{"deps":["MID"]},"MID":{"deps":["TARGET"]},"TARGET":{"target":True}},"target_records":[]},{"selected":["SAFE"]},{"selected":["SAFE","DERIVED"]},fr)
    add("F01","target_record_aggregation",{"features":{"SAFE":{"records":["OTHER_R"]},"AGG":{"records":["TARGET_R","OTHER_R"]}},"target_records":["TARGET_R"]},{"selected":["SAFE"]},{"selected":["SAFE","AGG"]},fr)
    add("F01","missing_dependency",{"features":{"SAFE":{"deps":[]},"UNKNOWN":{"deps":None}},"target_records":[]},{"selected":["SAFE"]},{"selected":["SAFE","UNKNOWN"]},fr,True)
    def feature(a,d,r,deps=None):return {"acquired_at":a,"processing_delay":d,"released_at":r,"deps":deps or []}
    tr="Ready time is max(acquired_at + processing_delay, released_at, dependency ready times). Every selected feature must be ready by cutoff under matching-scope evidence. Missing times remain unresolved."
    add("F02","release_delay",{"features":{"SAFE":feature(1,0,1),"LATE":feature(2,1,12)}},{"selected":["SAFE"]},{"selected":["SAFE","LATE"]},tr)
    add("F02","latest_dependency",{"features":{"SAFE":feature(1,0,1),"A":feature(2,0,2),"B":feature(3,9,3),"DERIVED":feature(3,0,3,["A","B"])}},{"selected":["SAFE"]},{"selected":["SAFE","DERIVED"]},tr)
    add("F02","current_scope_late",{"features":{"SAFE":feature(1,0,1),"LATE":feature(2,10,2)}},{"selected":["SAFE"]},{"selected":["SAFE","LATE"]},tr)
    add("F02","missing_release",{"features":{"SAFE":feature(1,0,1),"UNKNOWN":feature(1,0,None)}},{"selected":["SAFE"]},{"selected":["SAFE","UNKNOWN"]},tr,True)
    for arch,phase,partition in [("imputer_records","imputation","training"),("selector_records","feature_selection","training"),("calibration_records","calibration","calibration_development")]:
        add("F03",arch,{"phase":phase,"allowed_fit_partition":partition,"records":{"A":{"partition":partition},"B":{"partition":"final_heldout"}}},{"fit_record_ids":["A"]},{"fit_record_ids":["A","B"]},"Every fit_record_id must have the scoped allowed_fit_partition for this phase. Unknown roles remain unresolved.")
    add("F03","group_overlap",{"records":{"A":{"group":"G1"},"B":{"group":"G1"},"C":{"group":"G2"}}},{"train_ids":["A"],"heldout_ids":["C"]},{"train_ids":["A"],"heldout_ids":["B"]},"Train and held-out groups must be disjoint; compare group IDs, not just record IDs.")
    vr="A positive variance-analysis claim requires a performed design_aware_variance report completed by cutoff. Weighted point summaries or plans do not establish this. This contract does not certify estimator mathematics."
    add("F04","weighted_points_not_variance",{"reports":[{"performed":True,"method":"weighted_point_summary","completed_at":4}],"ledger_complete":True},{"variance_analysis_performed":False},{"variance_analysis_performed":True},vr)
    add("F04","component_weight_coverage",{"required_components":["interview","exam"],"required_domain":"exam_eligible","weights":{"W_EXAM":{"components":["interview","exam"],"domain":"exam_eligible"},"W_INTERVIEW":{"components":["interview"],"domain":"interview_eligible"}}},{"weight_id":"W_EXAM"},{"weight_id":"W_INTERVIEW"},"Weight components must cover required_components and its domain must equal required_domain. This is a synthetic rule, not actual NHANES guidance.")
    add("F04","proposed_not_executed_variance",{"reports":[{"performed":False,"method":"design_aware_variance","completed_at":None}],"ledger_complete":True},{"variance_analysis_performed":False},{"variance_analysis_performed":True},vr)
    add("F04","population_scope",{"established_domains":["adult_exam_eligible"]},{"population_domain":"adult_exam_eligible"},{"population_domain":"all_ages_national"},"The population_domain must belong to established_domains; scope matching is not evidence of population inferential validity.")
    pr="requested_action=none is no request. Otherwise approval must match action, scope, actor role and current contract hash, have authorization=approved, be effective and unexpired at cutoff and not revoked. No applicable approval in a complete registry means no permission."
    base={"actor_role":"analyst","contract_hash":"CURRENT","registry_complete":True}
    def approval(**kw):
        x={"action":"fit","authorization":"approved","actor_role":"analyst","effective_at":1,"expires_at":20,"revoked":False,"contract_hash":"CURRENT"};x.update(kw);return x
    for arch,a,good_action in [("withheld",approval(authorization="withheld"),"none"),("expired",approval(expires_at=8),"none"),("wrong_action_role",approval(action="summarize"),"summarize"),("stale_binding",approval(contract_hash="OLD"),"none")]:
        add("F05",arch,{**base,"approvals":[a]},{"requested_action":good_action},{"requested_action":"fit"},pr)
    er="A positive external-validation claim requires a performed artifact completed by cutoff with evaluation IDs disjoint from training IDs. Planned/future/overlapping artifacts do not support it. An incomplete ledger without a witness remains unresolved. False means withholding a positive assertion, not proving no event occurred."
    for arch,artifact,complete in [("overlapping_external_data",[{"performed":True,"completed_at":4,"evaluation_ids":["B","C"]}],True),("future_validation",[{"performed":True,"completed_at":12,"evaluation_ids":["C","D"]}],True),("planned_validation",[{"performed":False,"completed_at":None,"evaluation_ids":["C","D"]}],True),("incomplete_validation_ledger",[],False)]:
        add("F06",arch,{"training_ids":["A","B"],"validations":artifact,"ledger_complete":complete},{"external_validation_performed":False},{"external_validation_performed":True},er,not complete)
    return bank

def schema_errors(c,p):
    schema=c["proposal_schema"]
    if not isinstance(p,dict) or set(p)!=set(schema):return ["wrong_fields"]
    errors=[]
    for k,s in schema.items():
        v=p[k];kind=s["type"]
        if kind=="boolean":ok=type(v) is bool
        elif kind=="string":ok=isinstance(v,str) and bool(v.strip())
        else:ok=isinstance(v,list) and (bool(v) or s["allow_empty"]) and all(isinstance(x,str) and x.strip() for x in v) and len(v)==len(set(v))
        if not ok:errors.append("wrong_type_or_list:"+k)
    return errors

def facts(c):
    rows=[x for x in c["evidence"] if x["scope_id"]==c["scope_id"]]
    if len(rows)!=1:raise ValueError("Bundled cases require exactly one scoped fact bundle")
    return rows[0]["content"]

# Evaluator: artifact+facts only, no guard decision input.
def evaluate(c,p):
    errors=schema_errors(c,p)
    if errors:return {"verdict":U,"pipeline":"schema_failure","findings":errors,"trace":[]}
    f=facts(c);fam=c["family"];trace=[];cut=c["cutoff"]
    def done(v,why):return {"verdict":v,"pipeline":"assessable" if v!=U else "evidence_insufficient","findings":[] if v==T else [why],"trace":trace,"rule_id":c["rule_id"],"independent_scientific_validity":"NOT_ESTABLISHED"}
    def recurse(name,ancestors):
        if name in ancestors:return U,None
        node=f["features"].get(name)
        if node is None:return U,None
        if fam=="F01":
            if node.get("target") is True or set(node.get("records",[]))&set(f["target_records"]):return F,None
            deps=node.get("deps",[])
            if deps is None:return U,None
            ss=[recurse(x,ancestors+[name])[0] for x in deps]
            return (F if F in ss else U if U in ss else T),None
        vv=[node.get("acquired_at"),node.get("processing_delay"),node.get("released_at")]
        if not all(type(x) in (int,float) for x in vv):return U,None
        dd=[recurse(x,ancestors+[name]) for x in node.get("deps",[])]
        if any(s==U for s,_ in dd):return U,None
        ready=max([vv[0]+vv[1],vv[2]]+[x for _,x in dd]);return (T if ready<=cut else F),ready
    if fam in ("F01","F02"):
        ss=[]
        for name in p["selected"]:
            state,ready=recurse(name,[]);ss.append(state);trace.append({"feature":name,"state":state,"ready":ready})
        return done(F if F in ss else U if U in ss else T,"eligibility")
    if fam=="F03":
        if "fit_record_ids" in p:
            ss=[]
            for rid in p["fit_record_ids"]:
                part=f["records"].get(rid,{}).get("partition");state=U if part is None else T if part==f["allowed_fit_partition"] else F;ss.append(state);trace.append({"record":rid,"partition":part,"state":state})
            return done(F if F in ss else U if U in ss else T,"fit_boundary")
        if any(x not in f["records"] for x in p["train_ids"]+p["heldout_ids"]):return done(U,"unknown_record")
        a={f["records"][x]["group"] for x in p["train_ids"]};b={f["records"][x]["group"] for x in p["heldout_ids"]};trace.append({"overlap":sorted(a&b)});return done(F if a&b else T,"group_overlap")
    if fam=="F04":
        if "weight_id" in p:
            w=f["weights"].get(p["weight_id"])
            if w is None:return done(U,"unknown_weight")
            miss=set(f["required_components"])-set(w["components"]);ok=not miss and w["domain"]==f["required_domain"];trace.append({"missing_components":sorted(miss),"domain_matches":w["domain"]==f["required_domain"]});return done(T if ok else F,"weight_scope")
        if "population_domain" in p:return done(T if p["population_domain"] in f["established_domains"] else F,"population_scope")
        if not p["variance_analysis_performed"]:return done(T,"withheld_positive_claim")
        ws=[i for i,r in enumerate(f["reports"]) if r.get("performed") is True and r.get("method")=="design_aware_variance" and type(r.get("completed_at")) in (int,float) and r["completed_at"]<=cut];trace.append({"witnesses":ws});return done(T if ws else F if f["ledger_complete"] else U,"variance_claim")
    if fam=="F05":
        if p["requested_action"]=="none":return done(T,"no_request")
        ws=[]
        for i,a in enumerate(f["approvals"]):
            ok=a.get("action")==p["requested_action"] and a.get("authorization")=="approved" and a.get("actor_role")==f["actor_role"] and type(a.get("effective_at")) in (int,float) and a["effective_at"]<=cut and type(a.get("expires_at")) in (int,float) and a["expires_at"]>=cut and a.get("revoked") is False and a.get("contract_hash")==f["contract_hash"]
            trace.append({"approval":i,"applicable":ok})
            if ok:ws.append(i)
        return done(T if ws else F if f["registry_complete"] else U,"permission")
    if not p["external_validation_performed"]:return done(T,"withheld_positive_claim")
    ws=[]
    for i,a in enumerate(f["validations"]):
        overlap=set(a.get("evaluation_ids",[]))&set(f["training_ids"]);ok=a.get("performed") is True and type(a.get("completed_at")) in (int,float) and a["completed_at"]<=cut and bool(a.get("evaluation_ids")) and not overlap;trace.append({"artifact":i,"overlap":sorted(overlap),"applicable":ok})
        if ok:ws.append(i)
    return done(T if ws else F if f["ledger_complete"] else U,"validation_claim")

# Acceptance support implementation is separate from evaluate; semantics remain shared/authored.
def guard_support(c,p):
    if schema_errors(c,p):return U
    f=facts(c);fam=c["family"];cut=c["cutoff"]
    if fam in ("F01","F02"):
        graph=f["features"];states={};times={}
        for _ in range(len(graph)+1):
            for name,node in graph.items():
                if name in states:continue
                deps=node.get("deps",[])
                if fam=="F01" and (node.get("target") is True or set(node.get("records",[]))&set(f["target_records"])):states[name]=F;continue
                if deps is None:states[name]=U;continue
                if any(x not in graph for x in deps):states[name]=U;continue
                if not all(x in states for x in deps):continue
                if fam=="F01":states[name]=F if any(states[x]==F for x in deps) else U if any(states[x]==U for x in deps) else T
                else:
                    numbers=[node.get("acquired_at"),node.get("processing_delay"),node.get("released_at")]
                    if not all(type(x) in (int,float) for x in numbers) or any(states[x]==U for x in deps):states[name]=U;continue
                    times[name]=max([numbers[0]+numbers[1],numbers[2]]+[times[x] for x in deps]);states[name]=T if times[name]<=cut else F
        ss=[states.get(x,U) for x in p["selected"]];return F if F in ss else U if U in ss else T
    if fam=="F03":
        if "fit_record_ids" in p:
            roles=[f["records"].get(x,{}).get("partition") for x in p["fit_record_ids"]]
            if any(x is not None and x!=f["allowed_fit_partition"] for x in roles):return F
            return U if None in roles else T
        if any(x not in f["records"] for x in p["train_ids"]+p["heldout_ids"]):return U
        train_groups=[f["records"][x]["group"] for x in p["train_ids"]]
        return F if any(f["records"][x]["group"] in train_groups for x in p["heldout_ids"]) else T
    if fam=="F04":
        if "weight_id" in p:
            item=f["weights"].get(p["weight_id"])
            if item is None:return U
            return T if all(x in item["components"] for x in f["required_components"]) and item["domain"]==f["required_domain"] else F
        if "population_domain" in p:return T if any(p["population_domain"]==x for x in f["established_domains"]) else F
        if p["variance_analysis_performed"] is False:return T
        for r in f["reports"]:
            if r.get("performed") is True and r.get("method")=="design_aware_variance" and type(r.get("completed_at")) in (int,float) and r["completed_at"]-cut<=0:return T
        return F if f["ledger_complete"] else U
    if fam=="F05":
        action=p["requested_action"]
        if action=="none":return T
        for a in f["approvals"]:
            if a.get("action")!=action or a.get("authorization")!="approved" or a.get("revoked") is not False:continue
            if a.get("actor_role")!=f["actor_role"] or a.get("contract_hash")!=f["contract_hash"]:continue
            if type(a.get("effective_at")) in (int,float) and type(a.get("expires_at")) in (int,float) and a["effective_at"]<=cut<=a["expires_at"]:return T
        return F if f["registry_complete"] else U
    if p["external_validation_performed"] is False:return T
    for a in f["validations"]:
        if a.get("performed") is not True or type(a.get("completed_at")) not in (int,float) or a["completed_at"]>cut:continue
        if a.get("evaluation_ids") and all(x not in f["training_ids"] for x in a["evaluation_ids"]):return T
    return F if f["ledger_complete"] else U

def patch(c,p,target):
    return {"context_id":c["context_id"],"context_sha256":sha(c),"proposal_sha256":sha(p),"operations":[{"field":k,"old_value":p[k],"new_value":target[k],"evidence_ids":[r["evidence_id"] for r in c["evidence"] if r["scope_id"]==c["scope_id"]],"rationale":"Use the applicable evidence and rule."} for k in p if not same(p[k],target[k])]}

def apply(c,p,raw,guarded):
    def reject(reason,candidate=None):return {"path":"fallback_retained_input","accepted":False,"reasons":[reason],"proposed_candidate":candidate,"artifact":copy.deepcopy(p),"execution_authorized":False}
    if schema_errors(c,p):return reject("initial_schema_failure")
    if not isinstance(raw,dict) or set(raw)!={"context_id","context_sha256","proposal_sha256","operations"}:return reject("patch_schema_failure")
    if raw["context_id"]!=c["context_id"] or raw["context_sha256"]!=sha(c) or raw["proposal_sha256"]!=sha(p):return reject("identity_or_hash_failure")
    if not isinstance(raw["operations"],list) or len(raw["operations"])>len(p):return reject("operation_count")
    candidate=copy.deepcopy(p);seen=set()
    scoped={r["evidence_id"] for r in c["evidence"] if r["scope_id"]==c["scope_id"]}
    for op in raw["operations"]:
        if not isinstance(op,dict) or set(op)!={"field","old_value","new_value","evidence_ids","rationale"}:return reject("operation_schema")
        key=op["field"]
        if not isinstance(key,str) or key not in p or key in seen:return reject("unknown_or_duplicate_field")
        seen.add(key)
        if not same(op["old_value"],p[key]):return reject("stale_precondition")
        ids=op["evidence_ids"]
        if not isinstance(ids,list) or not all(isinstance(x,str) for x in ids) or len(ids)!=len(set(ids)):return reject("evidence_list_type")
        if not isinstance(op["rationale"],str) or not op["rationale"].strip():return reject("missing_rationale")
        candidate[key]=copy.deepcopy(op["new_value"])
        if guarded and (not ids or not set(ids).issubset(scoped)):return reject("inapplicable_evidence",candidate)
    if schema_errors(c,candidate):return reject("candidate_schema_failure",candidate)
    if guarded and raw["operations"] and guard_support(c,candidate)!=T:return reject("unsupported_candidate",candidate)
    return {"path":"no_op" if not raw["operations"] else "applied_change","accepted":True,"reasons":[],"proposed_candidate":candidate,"artifact":candidate,"execution_authorized":False}

def assess_paths(c,p,raw):
    outputs={}
    for name,guarded in (("interface_only",False),("evidence_guarded",True)):
        action=apply(c,p,raw,guarded)
        outputs[name]={"action":action,"accepted_artifact_assessment":evaluate(c,action["artifact"]),"proposed_candidate_assessment":evaluate(c,action["proposed_candidate"]) if action["proposed_candidate"] is not None else None}
    return {"raw_patch_sha256":sha(raw),"same_raw_patch_both_paths":True,"outputs":outputs}

def check():
    records=[]
    for item in contexts():
        c=item["public"];good=item["valid_or_conservative"];bad=item["counterpart"]
        assert evaluate(c,good)["verdict"]==T and evaluate(c,bad)["verdict"]==item["counterpart_expected"]
        assert guard_support(c,good)==T and guard_support(c,bad)==item["counterpart_expected"]
        correction=assess_paths(c,bad,patch(c,bad,good))
        assert all(x["accepted_artifact_assessment"]["verdict"]==T for x in correction["outputs"].values())
        harmful=assess_paths(c,good,patch(c,good,bad))
        assert harmful["outputs"]["interface_only"]["action"]["accepted"]
        assert not harmful["outputs"]["evidence_guarded"]["action"]["accepted"]
        assert harmful["outputs"]["evidence_guarded"]["accepted_artifact_assessment"]["verdict"]==T
        noop=patch(c,bad,bad);retained=assess_paths(c,bad,noop)
        assert all(x["accepted_artifact_assessment"]["verdict"]==item["counterpart_expected"] for x in retained["outputs"].values())
        stale=patch(c,bad,good);stale["context_sha256"]="stale"
        assert not apply(c,bad,stale,False)["accepted"]
        wrong=patch(c,bad,good)
        for op in wrong["operations"]:op["evidence_ids"]=[r["evidence_id"] for r in c["evidence"] if r["scope_id"]!=c["scope_id"]]
        assert not apply(c,bad,wrong,True)["accepted"]
        duplicate=patch(c,bad,good);duplicate["operations"]*=2
        assert not apply(c,bad,duplicate,False)["accepted"]
        records.append({"context_id":c["context_id"],"result":"PASS"})
    # Independent outcome check can detect a deliberately bypassed guard acceptance mistake.
    x=contexts()[0];fault=evaluate(x["public"],x["counterpart"])
    assert fault["verdict"]==F
    # Positive support checks for claims and permissions.
    v=copy.deepcopy(contexts()[12]["public"]);v["evidence"][0]["content"]["reports"]=[{"performed":True,"method":"design_aware_variance","completed_at":4}]
    assert evaluate(v,{"variance_analysis_performed":True})["verdict"]==guard_support(v,{"variance_analysis_performed":True})==T
    e=copy.deepcopy(contexts()[20]["public"]);e["evidence"][0]["content"]["validations"]=[{"performed":True,"completed_at":4,"evaluation_ids":["C","D"]}]
    assert evaluate(e,{"external_validation_performed":True})["verdict"]==guard_support(e,{"external_validation_performed":True})==T
    return {"status":"PASS_INTEGRATED_OFFLINE_DEVELOPMENT_CHECK_ONLY","contexts":len(records),"context_results":records,"model_calls":0,"heldout_evaluation":False,"independent_scientific_validation":False,"fault_injection_detected":True,"limits":"Authored fixtures and shared semantics; not completeness/security/effectiveness proof."}

def initial_inputs():
    for item in contexts():
        c=item["public"]
        for role in ("valid_or_conservative","counterpart"):
            p=item[role];pid="P"+sha({"context":c["context_id"],"role":role})[:12].upper()
            yield c,p,pid,role

def prompts(c,p,stream):
    task={"context":c,"initial_proposal":p}
    common="Review the synthetic proposal against its applicable evidence and rule. Preserve supported content and report uncertainty rather than inventing facts. No code execution or real study permission."
    if stream=="structure_feedback":common+=" Structural findings: "+json.dumps(schema_errors(c,p))
    if stream in ("evidence_critic","patch_critic"):common+=" Check scope, dependencies, timestamps, partition roles, approvals and empirical claim support. Cite evidence IDs for requested changes; do not invent criticism."
    review=[{"role":"system","content":common},{"role":"user","content":json.dumps(task)}]
    if stream=="patch_critic":
        spec={"context_id":c["context_id"],"context_sha256":sha(c),"proposal_sha256":sha(p),"operations":[{"field":"one existing field","old_value":"exact old JSON value","new_value":"proposed JSON value","evidence_ids":["applicable source ID"],"rationale":"brief evidence-backed justification"}]}
        instruction="Return only a JSON patch with this exact envelope/operation schema. Use operations=[] if no justified change. Do not copy placeholder values: "+json.dumps(spec)
    else:instruction="Return only the complete revised proposal JSON, using exactly proposal_schema. Retain correct decisions. If evidence is insufficient, do not invent support or approval."
    return review,task,instruction

def prepare(directory):
    directory.mkdir(parents=True,exist_ok=False);jobs=[];author=[]
    for c,p,pid,role in initial_inputs():
        author.append({"proposal_id":pid,"context_id":c["context_id"],"author_role":role,"author_evaluator_state":evaluate(c,p)["verdict"]})
        for stream in STREAMS:
            review,task,instruction=prompts(c,p,stream)
            jobs.append({"unit":pid+"__"+stream+"__42","proposal_id":pid,"context":c,"initial_proposal":p,"stream":stream,"seed":42,"review_messages":review,"revision_task":task,"revision_instruction":instruction})
    plan={"version":VERSION,"scope":"DEVELOPMENT_ONLY_NOT_CONFIRMATORY","model":"p6-qwen3-8b","base_url":"http://127.0.0.1:8010/v1","seeds":[42],"temperature":0.2,"max_tokens":1024,"timeout_seconds":300,"retries":0,"contexts":24,"inputs":48,"generator_streams":list(STREAMS),"workflow_units":len(jobs),"max_generation_calls":len(jobs)*2,"patch_paths_share_generation":True,"jobs_sha256":sha(jobs),"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"execution_authorized":False}
    write(directory/"jobs.json",jobs);write(directory/"plan.json",plan);write(directory/"AUTHOR_ONLY_input_states.json",author);write(directory/"offline_check.json",check())
    print(json.dumps({"status":"PREPARED_NOT_EXECUTED","directory":str(directory),"plan_sha256":sha(plan),"units":len(jobs),"max_generation_calls":plan["max_generation_calls"],"model_calls_made":0},indent=2))

def run(plan_dir,output_dir,approved_hash):
    plan=json.loads((plan_dir/"plan.json").read_text());jobs=json.loads((plan_dir/"jobs.json").read_text())
    if approved_hash!=sha(plan):raise SystemExit("Approval hash differs from exact plan; no calls made.")
    if sha(jobs)!=plan["jobs_sha256"]:raise SystemExit("Job manifest changed; no calls made.")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=plan["script_sha256"]:raise SystemExit("Runner changed; prepare/review a fresh plan.")
    if output_dir.exists():raise SystemExit("Output exists; no overwrite or automatic resume.")
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));key=os.environ.get("OPENAI_API_KEY","")
    def request(route,payload=None):
        headers={"Content-Type":"application/json"}
        if key:headers["Authorization"]="Bearer "+key
        req=urllib.request.Request(plan["base_url"]+route,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        with opener.open(req,timeout=plan["timeout_seconds"]) as response:return json.load(response)
    try:models=request("/models")
    except Exception as exc:raise SystemExit("Model discovery failed: "+type(exc).__name__+". No generations; credentials/error bodies not printed.")
    if plan["model"] not in [x.get("id") for x in models.get("data",[])]:raise SystemExit("Intended model absent; no substitution and no generations.")
    output_dir.mkdir(parents=True);write(output_dir/"plan.json",plan);counter=0;records=[]
    def completion(messages,seed,unit,stage):
        nonlocal counter
        if counter>=plan["max_generation_calls"]:raise RuntimeError("Request ceiling reached")
        payload={"model":plan["model"],"messages":messages,"temperature":plan["temperature"],"max_tokens":plan["max_tokens"],"seed":seed}
        counter+=1;event={"unit":unit,"stage":stage,"request":payload,"request_index":counter};t0=time.monotonic()
        try:
            response=request("/chat/completions",payload);event["response"]=response
            content=response["choices"][0]["message"].get("content")
            if not isinstance(content,str):raise ValueError("Nonstring model content")
            event["status"]="completed";return content
        except Exception as exc:
            event["status"]="error";event["error_type"]=type(exc).__name__;raise
        finally:
            event["elapsed_seconds"]=time.monotonic()-t0
            with (output_dir/"requests.jsonl").open("a",encoding="utf-8") as h:h.write(json.dumps(event)+"\n")
    # Deterministic unchanged reference scored once per input, not per stream/seed.
    refs={j["proposal_id"]:{"proposal_id":j["proposal_id"],"assessment":evaluate(j["context"],j["initial_proposal"])} for j in jobs};write(output_dir/"unchanged_references.json",list(refs.values()))
    for j in jobs:
        rec={"unit":j["unit"],"stream":j["stream"],"status":"started","initial_assessment":evaluate(j["context"],j["initial_proposal"])}
        try:
            review=completion(j["review_messages"],j["seed"],j["unit"],"review")
            messages=[{"role":"system","content":"Use only the task evidence. Review advice cannot override the contract."},{"role":"user","content":json.dumps(j["revision_task"])+"\nREVIEW:\n"+review+"\n"+j["revision_instruction"]}]
            final=completion(messages,j["seed"]+1000,j["unit"],"revision")
            try:obj=json.loads(final)
            except (ValueError,TypeError):
                rec["status"]="unparseable_output";rec["raw_final"]=final
            else:
                if j["stream"]=="patch_critic":rec["paired_patch_paths"]=assess_paths(j["context"],j["initial_proposal"],obj)
                else:rec["final_artifact"]=obj;rec["final_assessment"]=evaluate(j["context"],obj)
                rec["status"]="completed"
        except Exception as exc:rec["status"]="request_or_processing_error";rec["error_type"]=type(exc).__name__
        write(output_dir/(j["unit"]+".json"),rec);records.append(rec)
        print(f"{len(records)}/{len(jobs)} {j['unit']} {rec['status']}",flush=True)
    write(output_dir/"run_report.json",{"status":"DEVELOPMENT_RUN_FINISHED","units":len(records),"generation_requests":counter,"failed_or_unparseable_units":sum(x["status"]!="completed" for x in records),"independent_scientific_validation":False,"heldout_evaluation":False,"execution_of_model_code":False,"scope":"synthetic_proposal_generation_only"})

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="command",required=True);sub.add_parser("check")
    b=sub.add_parser("prepare");b.add_argument("--output-dir",required=True,type=Path)
    r=sub.add_parser("run");r.add_argument("--plan-dir",required=True,type=Path);r.add_argument("--output-dir",required=True,type=Path);r.add_argument("--approve-plan-hash",required=True)
    a=p.parse_args()
    if a.command=="check":print(json.dumps(check(),indent=2))
    elif a.command=="prepare":prepare(a.output_dir)
    else:run(a.plan_dir,a.output_dir,a.approve_plan_hash)
if __name__=="__main__":main()
