"""Read-only scan of saved request logs (requests.jsonl) for reasoning output and truncation.
Usage: python p6_scan_requests.py RUN_DIR [RUN_DIR ...]   (prints counts only; no prompt or response text)"""
import collections, json, statistics, sys
from pathlib import Path
for d in map(Path, sys.argv[1:]):
    f = d / "requests.jsonl"
    if not f.exists():
        continue
    st = collections.defaultdict(lambda: {"n": 0, "finish": collections.Counter(), "tok": [], "reasoning_field": 0, "think_tag": 0, "errors": 0})
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line); s = st[e.get("stage")]; s["n"] += 1
        if e.get("status") != "completed":
            s["errors"] += 1; continue
        ch = e["response"]["choices"][0]; m = ch["message"]; c = m.get("content") or ""
        s["finish"][ch["finish_reason"]] += 1; s["tok"].append(e["response"]["usage"]["completion_tokens"])
        s["reasoning_field"] += bool(m.get("reasoning_content") or m.get("reasoning")); s["think_tag"] += ("<think>" in c or "</think>" in c)
    plan = {}
    try:
        plan = json.loads((d / "plan.json").read_text())
    except Exception:
        pass
    print(json.dumps({"run_dir": str(d), "model": plan.get("model"), "units": plan.get("workflow_units"), "thinking_setting_in_plan": plan.get("thinking", "not_recorded"),
                      "stages": {k: {"n": v["n"], "errors": v["errors"], "finish": dict(v["finish"]), "median_completion_tokens": statistics.median(v["tok"]) if v["tok"] else None,
                                     "max_completion_tokens": max(v["tok"]) if v["tok"] else None, "responses_with_reasoning_field": v["reasoning_field"],
                                     "responses_with_think_tags": v["think_tag"]} for k, v in st.items()}}))
