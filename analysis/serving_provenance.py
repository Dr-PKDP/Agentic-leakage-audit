"""Serving provenance of the three models, collected from the archived run records.

Reads the model entry and server version that each run stored in its summary or run report, and the
server fingerprint that the responses carry in the request logs. Writes results/serving_provenance.json.

The run records fix the serving identifier, the local model directory, the context length the server was
started with and the server version. The weight revision, the served dtype, the quantization setting and the
SHA-256 of every weight shard were recorded afterwards on the serving host and are deposited in
results/model_weights.json; they are merged here.

Usage: python analysis/serving_provenance.py [--out DIR]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def walk(obj, models, versions):
    if isinstance(obj, dict):
        if obj.get("object") == "model" or ("root" in obj and "max_model_len" in obj):
            models.setdefault(obj["id"], {}).update(
                {"root": obj.get("root"), "max_model_len": obj.get("max_model_len")})
        if set(obj) == {"version"}:
            versions.add(obj["version"])
        for v in obj.values():
            walk(v, models, versions)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, models, versions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=RES)
    a = ap.parse_args()

    entries = {}
    for path in sorted(RES.rglob("summary.json")) + sorted(RES.rglob("run_report.json")):
        models, versions = {}, set()
        walk(json.loads(path.read_text(encoding="utf-8")), models, versions)
        for mid, rec in models.items():
            e = entries.setdefault(mid, {"serving_identifier": mid, "runs": []})
            e.update({k: v for k, v in rec.items() if v is not None})
            if versions:
                e["server_version"] = sorted(versions)[0]
            e["runs"].append(str(path.parent.relative_to(RES)))

    for path in sorted(RES.rglob("requests.jsonl")):
        with path.open(encoding="utf-8") as h:
            for line in h:
                resp = json.loads(line).get("response") or {}
                if isinstance(resp, dict) and resp.get("model") and resp.get("system_fingerprint"):
                    e = entries.setdefault(resp["model"], {"serving_identifier": resp["model"], "runs": []})
                    e.setdefault("server_fingerprints", [])
                    if resp["system_fingerprint"] not in e["server_fingerprints"]:
                        e["server_fingerprints"].append(resp["system_fingerprint"])
                    break

    weights = json.loads((RES / "model_weights.json").read_text(encoding="utf-8"))["models"]
    for e in entries.values():
        e["runs"] = sorted(set(e["runs"]))
        w = weights.get(e["serving_identifier"], {})
        e["weight_revision"] = w.get("download_revision")
        e["served_dtype"] = w.get("served_dtype")
        e["quantization"] = w.get("quantization")
        e["weight_shards"] = w.get("shards")

    out = {"note": ("Run-level fields are collected from the archived run records. The weight revision, served "
                    "dtype and quantization setting were recorded on the serving host and come from "
                    "results/model_weights.json, which also holds the SHA-256 of every shard. The context "
                    "length is the value the server was started with, not a property of the model."),
           "models": [entries[k] for k in sorted(entries)]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "serving_provenance.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for e in out["models"]:
        print(f"{e['serving_identifier']:16s} {str(e.get('root')):58s} len={e.get('max_model_len')} "
              f"vllm={e.get('server_version')} fp={e.get('server_fingerprints')}")


if __name__ == "__main__":
    main()
