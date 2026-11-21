"""Direct-revision comparator: the reviser receives the context and the initial proposal with no review.

Two arms per context set, mirroring the revision formats of the critic-reviser workflows:
  full   the model returns a complete revised proposal (as in the self-review, structure-feedback and evidence-critic paths)
  patch  the model returns a JSON patch, scored under Gate A and Gate B on the same response (as in the patch path)

Settings match Experiment 3: revision limit 512 tokens, temperature 0.2, revision seed = review seed + 1000, original
revision instruction, server-default thinking mode. The core and label runners are imported unchanged and verified by hash.

Usage:  python p6_direct_revision.py check
        python p6_direct_revision.py prepare --output-dir NEW_DIR --context-set core24|nhanes --model ID --base-url URL
        python p6_direct_revision.py run --plan-dir DIR --output-dir NEW_DIR --approve-plan-hash HASH
"""
import argparse, hashlib, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "core_contexts")); sys.path.insert(0, str(HERE.parent / "label_contexts"))
import p6_integrated_development_v0_4 as v4
import p6_extended_v0_5 as ext

V4_SHA256 = ext.V4_SHA256
EXT_SHA256 = hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest()
VERSION = "p6_direct_revision_1"
ARMS = ("direct_full", "direct_patch")
sha = v4.sha


def file_sha(m):
    return hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()


def build_jobs(context_set, seeds):
    jobs = []
    for c, p, pid, role in ext.initial_inputs(ext.context_items(context_set)):
        for arm in ARMS:
            stream = "patch_critic" if arm == "direct_patch" else "self_review"
            _, task, instruction = v4.prompts(c, p, stream)
            for seed in seeds:
                jobs.append({"unit": f"{pid}__{arm}__{seed}", "proposal_id": pid, "author_role": role, "context": c, "initial_proposal": p,
                             "arm": arm, "seed": seed, "revision_task": task, "revision_instruction": instruction})
    return jobs


def check():
    jobs = build_jobs("core24", [42]) + build_jobs("nhanes", [42, 43])
    assert all("REVIEW" not in json.dumps(j["revision_task"]) for j in jobs)
    assert {j["arm"] for j in jobs} == set(ARMS)
    return {"status": "PASS", "core24_jobs": len(build_jobs("core24", [42])), "nhanes_jobs": len(build_jobs("nhanes", [42, 43])), "model_calls": 0}


def prepare(a):
    seeds = [int(x) for x in a.seeds.split(",")]
    jobs = build_jobs(a.context_set, seeds)
    plan = {"version": VERSION, "arm": "direct_revision_" + a.context_set, "context_set": a.context_set, "thinking": "default", "model": a.model,
            "base_url": a.base_url, "seeds": seeds, "temperature": 0.2, "max_tokens": a.revision_max_tokens, "timeout_seconds": 300, "retries": 0,
            "workers": a.workers, "arms": list(ARMS), "workflow_units": len(jobs), "max_generation_calls": len(jobs), "patch_paths_share_generation": True,
            "jobs_sha256": sha(jobs), "script_sha256": file_sha(sys.modules[__name__]), "v4_script_sha256": file_sha(v4), "ext_script_sha256": EXT_SHA256,
            "execution_authorized": False}
    d = a.output_dir; d.mkdir(parents=True, exist_ok=False)
    v4.write(d / "jobs.json", jobs); v4.write(d / "plan.json", plan)
    print(json.dumps({"status": "PREPARED_NOT_EXECUTED", "directory": str(d), "plan_sha256": sha(plan), "units": len(jobs),
                      "max_generation_calls": plan["max_generation_calls"], "model_calls_made": 0}, indent=2))


def run(a):
    plan = json.loads((a.plan_dir / "plan.json").read_text()); jobs = json.loads((a.plan_dir / "jobs.json").read_text())
    if a.approve_plan_hash != sha(plan): raise SystemExit("Approval hash differs from the exact plan; no calls made.")
    if sha(jobs) != plan["jobs_sha256"]: raise SystemExit("Job manifest changed; no calls made.")
    me = file_sha(sys.modules[__name__])
    if me != plan["script_sha256"]: raise SystemExit("Runner changed; prepare a fresh plan.")
    if file_sha(v4) != plan["v4_script_sha256"] or file_sha(v4) != V4_SHA256: raise SystemExit("Core runner differs from the verified file; no calls made.")
    if file_sha(ext) != plan["ext_script_sha256"]: raise SystemExit("Label runner differs from the planned file; no calls made.")
    if a.output_dir.exists(): raise SystemExit("Output exists; no overwrite or automatic resume.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})); key = os.environ.get("OPENAI_API_KEY", "")

    def request(route, payload=None, root=False):
        headers = {"Content-Type": "application/json"}
        if key: headers["Authorization"] = "Bearer " + key
        base = plan["base_url"][:-3] if root else plan["base_url"]
        req = urllib.request.Request(base + route, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        with opener.open(req, timeout=plan["timeout_seconds"]) as r: return json.load(r)

    try: models = request("/models")
    except Exception as exc: raise SystemExit("Model discovery failed: " + type(exc).__name__ + ". No generations.")
    if plan["model"] not in [x.get("id") for x in models.get("data", [])]: raise SystemExit("Intended model absent; no substitution.")
    out = a.output_dir; out.mkdir(parents=True); v4.write(out / "plan.json", plan); v4.write(out / "models.json", models)
    try: v4.write(out / "server_version.json", request("/version", root=True))
    except Exception: pass
    lock, plock = threading.Lock(), threading.Lock(); state = {"n": 0, "done": 0}; records = []

    def completion(messages, seed, unit):
        payload = {"model": plan["model"], "messages": messages, "temperature": plan["temperature"], "max_tokens": plan["max_tokens"], "seed": seed}
        with lock:
            if state["n"] >= plan["max_generation_calls"]: raise RuntimeError("Request ceiling reached")
            state["n"] += 1; idx = state["n"]
        event = {"unit": unit, "stage": "revision", "request": payload, "request_index": idx}; t0 = time.monotonic()
        try:
            resp = request("/chat/completions", payload); event["response"] = resp
            content = resp["choices"][0]["message"].get("content")
            if not isinstance(content, str): raise ValueError("Nonstring model content")
            event["status"] = "completed"; return content
        except Exception as exc:
            event["status"] = "error"; event["error_type"] = type(exc).__name__; raise
        finally:
            event["elapsed_seconds"] = time.monotonic() - t0
            with lock, (out / "requests.jsonl").open("a", encoding="utf-8") as h: h.write(json.dumps(event) + "\n")

    def work(j):
        rec = {"unit": j["unit"], "arm": j["arm"], "seed": j["seed"], "status": "started", "initial_assessment": ext.evaluate_ext(j["context"], j["initial_proposal"])}
        try:
            msgs = [{"role": "system", "content": "Use only the task evidence."},
                    {"role": "user", "content": json.dumps(j["revision_task"]) + "\n" + j["revision_instruction"]}]
            final = completion(msgs, j["seed"] + 1000, j["unit"])
            try: obj = json.loads(final)
            except (ValueError, TypeError): rec["status"] = "unparseable_output"; rec["raw_final"] = final
            else:
                if j["arm"] == "direct_patch": rec["paired_patch_paths"] = v4.assess_paths(j["context"], j["initial_proposal"], obj)
                else: rec["final_artifact"] = obj; rec["final_assessment"] = ext.evaluate_ext(j["context"], obj)
                rec["status"] = "completed"
        except Exception as exc: rec["status"] = "request_or_processing_error"; rec["error_type"] = type(exc).__name__
        v4.write(out / (j["unit"] + ".json"), rec)
        with plock:
            records.append(rec); state["done"] += 1; print(f"{state['done']}/{len(jobs)} {j['unit']} {rec['status']}", flush=True)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=plan["workers"]) as ex: list(ex.map(work, jobs))
    v4.write(out / "run_report.json", {"status": "RUN_FINISHED", "arm": plan["arm"], "units": len(records), "generation_requests": state["n"],
                                       "failed_or_unparseable_units": sum(x["status"] != "completed" for x in records),
                                       "wall_clock_seconds": time.monotonic() - t0, "execution_of_model_code": False})


def main():
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest="cmd", required=True); s.add_parser("check")
    b = s.add_parser("prepare"); b.add_argument("--output-dir", required=True, type=Path); b.add_argument("--context-set", choices=["core24", "nhanes"], required=True)
    b.add_argument("--seeds", default="42"); b.add_argument("--model", required=True); b.add_argument("--base-url", required=True)
    b.add_argument("--workers", type=int, default=8); b.add_argument("--revision-max-tokens", type=int, default=512)
    r = s.add_parser("run"); r.add_argument("--plan-dir", required=True, type=Path); r.add_argument("--output-dir", required=True, type=Path); r.add_argument("--approve-plan-hash", required=True)
    a = p.parse_args()
    if a.cmd == "check": print(json.dumps(check(), indent=2))
    elif a.cmd == "prepare": prepare(a)
    else: run(a)


if __name__ == "__main__":
    main()
