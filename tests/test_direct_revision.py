import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "experiments/direct_revision"
sys.path.insert(0, str(DIR))
import p6_direct_revision as d  # noqa: E402

v4, ext = d.v4, d.ext
ITEMS = {i["public"]["context_id"]: i for s in ("core24", "nhanes") for i in ext.context_items(s)}


class Oracle(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.endswith("/models"):
            self._send({"data": [{"id": "mock-model", "max_model_len": 4096}]})
        else:
            self._send({"version": "mock"})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = req["messages"][-1]["content"]
        assert "REVIEW" not in user
        task = json.loads(user.split("\n", 1)[0])
        c, p = task["context"], task["initial_proposal"]
        target = ITEMS[c["context_id"]]["valid_or_conservative"]
        out = json.dumps(v4.patch(c, p, target) if "JSON patch" in user else target)
        self._send({"choices": [{"index": 0, "message": {"role": "assistant", "content": out}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})


def test_direct_revision_pipeline(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Oracle)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    py = [sys.executable, "p6_direct_revision.py"]
    prep = json.loads(subprocess.run([*py, "prepare", "--output-dir", str(tmp_path / "plan"), "--context-set", "core24", "--model", "mock-model",
                                       "--base-url", url, "--workers", "2"], cwd=DIR, capture_output=True, text=True, check=True).stdout)
    assert prep["units"] == 96 and prep["max_generation_calls"] == 96
    subprocess.run([*py, "run", "--plan-dir", str(tmp_path / "plan"), "--output-dir", str(tmp_path / "run"),
                    "--approve-plan-hash", prep["plan_sha256"]], cwd=DIR, check=True, capture_output=True)
    ref = ROOT / "results/review_limit_2048/core24/outcomes.csv"
    out = subprocess.run([sys.executable, "analyze_direct_revision.py", "--plan-dir", str(tmp_path / "plan"), "--run-dir", str(tmp_path / "run"),
                          "--out-dir", str(tmp_path / "an"), "--reference", str(ref)], cwd=DIR, capture_output=True, text=True, check=True)
    s = json.loads((tmp_path / "an/summary.json").read_text())
    for p in ("direct_full", "direct_patch/interface_only", "direct_patch/evidence_guarded"):
        assert s["by_path"][p]["repair"] == [21, 21] and s["by_path"][p]["preserve"] == [24, 24] and s["by_path"][p]["harmful"] == 0
    assert "paired_vs_critic_reviser" in s
    server.shutdown()
