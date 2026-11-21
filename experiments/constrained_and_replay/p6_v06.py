"""P6 v0.6 runner: constrained decoding and review-replay arms on top of the verified v0.4 and v0.5 runners.

Imports p6_extended_v0_5 (hash-checked) and p6_integrated_development_v0_4 (hash-checked) unchanged and adds:
  --constrained            the revision request carries a JSON-schema response format built from the context's proposal schema
                           (full-proposal streams) or the patch envelope (patch stream); the revision is requested without thinking.
  --replay-source DIR      reviews are read from an earlier run (DIR/plans/SET and DIR/runs/SET/requests.jsonl); no review request is made.
  --truncate-review-tokens N
                           with --replay-source: each saved review is cut to its first N tokens with the serving model's own tokenizer
                           (0 keeps the full saved review). Only the revision request is generated.
Run records have the format of the earlier runs, so p6_extended_analyze.py reads them unchanged.
Generation needs the exact plan hash, never retries and never resumes.
"""
import argparse, hashlib, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p6_extended_v0_5 as x

v4 = x.v4
VERSION = "p6_v06"
V4_SHA256 = "1649d94540600146e4f562c48525b68f82813b2fa6e360c8fa881bbdb8b7cb83"
EXT_SHA256 = "7d0b3824a869d7d9c027facaa4cf339b32c046b47da6d3fdcb8d978d8e0d5ea8"
sha = v4.sha


def fsha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clarified_instruction(c, p, stream):
    if stream == "patch_critic":
        env = {"context_id": c["context_id"], "context_sha256": v4.sha(c), "proposal_sha256": v4.sha(p)}
        return ("Return only one JSON object, with no Markdown fence and no text before or after it. Its top-level keys are exactly "
                "context_id, context_sha256, proposal_sha256 and operations. Copy the first three values exactly: " + json.dumps(env) +
                ". operations is a list; each item has the keys field, old_value, new_value, evidence_ids and rationale, where field is one of " +
                json.dumps(list(p)) + ", old_value is the current value of that field and evidence_ids lists applicable source IDs. "
                "Use operations=[] if no justified change.")
    return ("Return only the complete revised proposal as one JSON object whose top-level keys are exactly " + json.dumps(list(c["proposal_schema"])) +
            ", with no wrapper object, no Markdown fence and no text before or after it. Retain correct decisions. "
            "If evidence is insufficient, do not invent support or approval.")


def response_schema(c, p, stream):
    kinds = {"boolean": {"type": "boolean"}, "string": {"type": "string", "minLength": 1},
             "string_list": {"type": "array", "items": {"type": "string", "minLength": 1}}}
    if stream != "patch_critic":
        sch = c["proposal_schema"]
        return {"type": "object", "properties": {k: kinds[s["type"]] for k, s in sch.items()}, "required": list(sch), "additionalProperties": False}
    value = {"anyOf": [{"type": "string"}, {"type": "boolean"}, {"type": "array", "items": {"type": "string"}}]}
    op = {"type": "object", "properties": {"field": {"enum": list(p)}, "old_value": value, "new_value": value,
                                           "evidence_ids": {"type": "array", "items": {"type": "string"}}, "rationale": {"type": "string", "minLength": 1}},
          "required": ["field", "old_value", "new_value", "evidence_ids", "rationale"], "additionalProperties": False}
    return {"type": "object", "properties": {"context_id": {"type": "string"}, "context_sha256": {"type": "string"}, "proposal_sha256": {"type": "string"},
                                             "operations": {"type": "array", "maxItems": len(p), "items": op}},
            "required": ["context_id", "context_sha256", "proposal_sha256", "operations"], "additionalProperties": False}


def http(base, key, route, payload=None, root=False, timeout=300):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    url = (base[:-3] if root else base) + route
    req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    with opener.open(req, timeout=timeout) as r:
        return json.load(r)


def saved_reviews(src_root, setname):
    """Map unit -> saved review text from an earlier run of the same context set."""
    plan_dir, run_dir = Path(src_root) / "plans" / setname, Path(src_root) / "runs" / setname
    jobs = json.loads((plan_dir / "jobs.json").read_text())
    reviews = {}
    with (run_dir / "requests.jsonl").open(encoding="utf-8") as h:
        for line in h:
            e = json.loads(line)
            if e.get("stage") == "review" and e.get("status") == "completed":
                reviews[e["unit"]] = e["response"]["choices"][0]["message"]["content"]
    return jobs, reviews


def prepare(a):
    key = os.environ.get("OPENAI_API_KEY", "")
    seeds = [int(s) for s in a.seeds.split(",")]
    jobs, notes = [], {}
    streams = [t for t in a.streams.split(",") if t] if a.streams else list(x.STREAMS)
    assert set(streams) <= set(x.STREAMS), streams
    if a.replay_source:
        src_jobs, reviews = saved_reviews(a.replay_source, a.context_set)
        counts = {"source_units": len(src_jobs), "with_saved_review": 0, "truncated": 0}
        for j in src_jobs:
            text = reviews.get(j["unit"])
            if not isinstance(text, str):
                continue
            counts["with_saved_review"] += 1
            n_full = None
            if a.truncate_review_tokens:
                tok = http(a.base_url, key, "/tokenize", {"model": a.model, "prompt": text, "add_special_tokens": False}, root=True)
                toks = tok["tokens"]; n_full = len(toks)
                if n_full > a.truncate_review_tokens:
                    text = http(a.base_url, key, "/detokenize", {"model": a.model, "tokens": toks[:a.truncate_review_tokens]}, root=True)["prompt"]
                    counts["truncated"] += 1
            k = dict(j); k.update(review_text=text, review_tokens_full=n_full, unit=j["unit"] + "__" + a.arm)
            if a.prompt_variant == "clarified":
                k["revision_instruction"] = clarified_instruction(j["context"], j["initial_proposal"], j["stream"])
            jobs.append(k)
        notes = counts
        calls_per_unit = 1
    else:
        items = x.context_items(a.context_set)
        for c, p, pid, role in x.initial_inputs(items):
            for stream in streams:
                for seed in seeds:
                    review, task, instruction = v4.prompts(c, p, stream)
                    if a.prompt_variant == "clarified":
                        instruction = clarified_instruction(c, p, stream)
                    jobs.append({"unit": f"{pid}__{stream}__{seed}", "proposal_id": pid, "author_role": role, "context": c, "initial_proposal": p, "stream": stream,
                                 "seed": seed, "review_messages": review, "revision_task": task, "revision_instruction": instruction})
        calls_per_unit = 2
    plan = {"version": VERSION, "scope": "DEVELOPMENT_ONLY_NOT_CONFIRMATORY", "arm": a.arm, "context_set": a.context_set, "thinking": a.thinking,
            "model": a.model, "base_url": a.base_url, "seeds": seeds, "temperature": 0.2, "max_tokens": a.revision_max_tokens, "review_max_tokens": a.review_max_tokens,
            "timeout_seconds": 300, "retries": 0, "workers": a.workers, "constrained": bool(a.constrained), "prompt_variant": a.prompt_variant,
            "replay_source": str(a.replay_source) if a.replay_source else None, "truncate_review_tokens": a.truncate_review_tokens, "replay_counts": notes,
            "generator_streams": streams, "workflow_units": len(jobs), "max_generation_calls": len(jobs) * calls_per_unit,
            "patch_paths_share_generation": True, "jobs_sha256": sha(jobs), "script_sha256": fsha(__file__), "v4_script_sha256": fsha(v4.__file__),
            "ext_script_sha256": fsha(x.__file__), "execution_authorized": False}
    d = a.output_dir; d.mkdir(parents=True, exist_ok=False)
    v4.write(d / "jobs.json", jobs); v4.write(d / "plan.json", plan)
    print(json.dumps({"status": "PREPARED_NOT_EXECUTED", "arm": a.arm, "directory": str(d), "plan_sha256": sha(plan), "units": len(jobs),
                      "max_generation_calls": plan["max_generation_calls"], "replay_counts": notes}, indent=2))


def run(a):
    plan = json.loads((a.plan_dir / "plan.json").read_text()); jobs = json.loads((a.plan_dir / "jobs.json").read_text())
    if a.approve_plan_hash != sha(plan): raise SystemExit("Approval hash differs from exact plan; no calls made.")
    if sha(jobs) != plan["jobs_sha256"]: raise SystemExit("Job manifest changed; no calls made.")
    if fsha(__file__) != plan["script_sha256"]: raise SystemExit("Runner changed; prepare a fresh plan.")
    if fsha(v4.__file__) != plan["v4_script_sha256"] or fsha(v4.__file__) != V4_SHA256: raise SystemExit("v0.4 runner differs from the verified file; no calls made.")
    if fsha(x.__file__) != plan["ext_script_sha256"] or fsha(x.__file__) != EXT_SHA256: raise SystemExit("v0.5 runner differs from the verified file; no calls made.")
    if a.output_dir.exists(): raise SystemExit("Output exists; no overwrite or automatic resume.")
    key = os.environ.get("OPENAI_API_KEY", "")
    try: models = http(plan["base_url"], key, "/models")
    except Exception as exc: raise SystemExit("Model discovery failed: " + type(exc).__name__ + ". No generations.")
    if plan["model"] not in [m.get("id") for m in models.get("data", [])]: raise SystemExit("Intended model absent; no substitution.")
    out = a.output_dir; out.mkdir(parents=True); v4.write(out / "plan.json", plan); v4.write(out / "models.json", models)
    try: v4.write(out / "server_version.json", http(plan["base_url"], key, "/version", root=True))
    except Exception: pass
    lock, plock = threading.Lock(), threading.Lock(); state = {"n": 0, "done": 0}; records = []
    replay = bool(plan["replay_source"])

    def completion(messages, seed, unit, stage, job):
        limit = plan["review_max_tokens"] if stage == "review" else plan["max_tokens"]
        payload = {"model": plan["model"], "messages": messages, "temperature": plan["temperature"], "max_tokens": limit, "seed": seed}
        revision_constrained = plan["constrained"] and stage == "revision"
        if plan["thinking"] == "off" or revision_constrained: payload["chat_template_kwargs"] = {"enable_thinking": False}
        if revision_constrained:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "p6_revision", "strict": True,
                                          "schema": response_schema(job["context"], job["initial_proposal"], job["stream"])}}
        with lock:
            if state["n"] >= plan["max_generation_calls"]: raise RuntimeError("Request ceiling reached")
            state["n"] += 1; idx = state["n"]
        event = {"unit": unit, "stage": stage, "request": payload, "request_index": idx}; t0 = time.monotonic()
        try:
            resp = http(plan["base_url"], key, "/chat/completions", payload); event["response"] = resp
            content = resp["choices"][0]["message"].get("content")
            if not isinstance(content, str): raise ValueError("Nonstring model content")
            event["status"] = "completed"; return content
        except Exception as exc:
            event["status"] = "error"; event["error_type"] = type(exc).__name__; raise
        finally:
            event["elapsed_seconds"] = time.monotonic() - t0
            with lock, (out / "requests.jsonl").open("a", encoding="utf-8") as h: h.write(json.dumps(event) + "\n")

    def work(j):
        rec = {"unit": j["unit"], "stream": j["stream"], "seed": j["seed"], "status": "started", "initial_assessment": x.evaluate_ext(j["context"], j["initial_proposal"])}
        try:
            review = j["review_text"] if replay else completion(j["review_messages"], j["seed"], j["unit"], "review", j)
            msgs = [{"role": "system", "content": "Use only the task evidence. Review advice cannot override the contract."},
                    {"role": "user", "content": json.dumps(j["revision_task"]) + "\nREVIEW:\n" + review + "\n" + j["revision_instruction"]}]
            final = completion(msgs, j["seed"] + 1000, j["unit"], "revision", j)
            try: obj = json.loads(final)
            except (ValueError, TypeError): rec["status"] = "unparseable_output"; rec["raw_final"] = final
            else:
                if j["stream"] == "patch_critic": rec["paired_patch_paths"] = v4.assess_paths(j["context"], j["initial_proposal"], obj)
                else: rec["final_artifact"] = obj; rec["final_assessment"] = x.evaluate_ext(j["context"], obj)
                rec["status"] = "completed"
        except Exception as exc: rec["status"] = "request_or_processing_error"; rec["error_type"] = type(exc).__name__
        v4.write(out / (j["unit"] + ".json"), rec)
        with plock:
            records.append(rec); state["done"] += 1; print(f"{state['done']}/{len(jobs)} {j['unit']} {rec['status']}", flush=True)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=plan["workers"]) as ex: list(ex.map(work, jobs))
    v4.write(out / "run_report.json", {"status": "DEVELOPMENT_RUN_FINISHED", "arm": plan["arm"], "units": len(records), "generation_requests": state["n"],
                                       "failed_or_unparseable_units": sum(r["status"] != "completed" for r in records),
                                       "wall_clock_seconds": time.monotonic() - t0, "independent_scientific_validation": False, "heldout_evaluation": False,
                                       "execution_of_model_code": False, "scope": "synthetic_proposal_generation_only"})


def check():
    """Offline: schema generation and replay machinery on all contexts; no model calls."""
    n = 0
    for name in ("core24", "nhanes"):
        for it in x.context_items(name):
            c = it["public"]
            for role in ("valid_or_conservative", "counterpart"):
                p = it[role]
                for stream in ("self_review", "patch_critic"):
                    s = response_schema(c, p, stream); json.dumps(s); n += 1
                    if stream != "patch_critic":
                        assert not v4.schema_errors(c, p) and set(s["properties"]) == set(p)
    return {"status": "PASS_OFFLINE", "schemas_built": n, "model_calls": 0, "v4_hash_ok": fsha(v4.__file__) == V4_SHA256, "ext_hash_ok": fsha(x.__file__) == EXT_SHA256}


def main():
    ap = argparse.ArgumentParser(description=__doc__); s = ap.add_subparsers(dest="cmd", required=True)
    s.add_parser("check")
    b = s.add_parser("prepare"); b.add_argument("--output-dir", required=True, type=Path); b.add_argument("--arm", required=True)
    b.add_argument("--context-set", choices=["core24", "nhanes"], required=True); b.add_argument("--thinking", choices=["default", "off"], default="default")
    b.add_argument("--seeds", default="42"); b.add_argument("--model", required=True); b.add_argument("--base-url", required=True); b.add_argument("--workers", type=int, default=8)
    b.add_argument("--review-max-tokens", type=int, default=2048); b.add_argument("--revision-max-tokens", type=int, default=512)
    b.add_argument("--prompt-variant", choices=["original", "clarified"], default="original"); b.add_argument("--constrained", action="store_true")
    b.add_argument("--streams", default="")
    b.add_argument("--replay-source", type=Path, default=None); b.add_argument("--truncate-review-tokens", type=int, default=0)
    r = s.add_parser("run"); r.add_argument("--plan-dir", required=True, type=Path); r.add_argument("--output-dir", required=True, type=Path); r.add_argument("--approve-plan-hash", required=True)
    a = ap.parse_args()
    if a.cmd == "check": print(json.dumps(check(), indent=2))
    elif a.cmd == "prepare": prepare(a)
    else: run(a)


if __name__ == "__main__":
    main()
