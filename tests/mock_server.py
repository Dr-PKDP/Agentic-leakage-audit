"""Minimal OpenAI-compatible server used to exercise the extended pipeline without a model."""
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import p6_extended_v0_5 as x

v4 = x.v4
ITEMS = {i["public"]["context_id"]: i for s in ("core24", "nhanes") for i in x.context_items(s)}


def make_handler(mode):
    rng = random.Random(1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.endswith("/models"):
                self._send({"data": [{"id": "mock-model", "root": "/mock", "max_model_len": 32768}]})
            elif self.path.endswith("/version"):
                self._send({"version": "mock"})
            else:
                self.send_error(404)

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            user = req["messages"][-1]["content"]
            thinking_off = req.get("chat_template_kwargs", {}).get("enable_thinking") is False
            msg = {"role": "assistant"}
            if "\nREVIEW:\n" in user:
                task = json.loads(user.split("\nREVIEW:\n")[0])
                context, proposal = task["context"], task["initial_proposal"]
                target = ITEMS[context["context_id"]]["valid_or_conservative"]
                if mode == "prefix" and context["family"] == "F07":
                    target = x.prefix_reviser(context, proposal)
                out = json.dumps(v4.patch(context, proposal, target) if "JSON patch" in user else target)
                msg["content"], finish = out, "stop"
            else:
                msg["content"], finish = "Review text. " * 60, "length"
            if not thinking_off and rng.random() < 0.5:
                msg["reasoning_content"] = "reasoning"
            usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
            self._send({"id": "mock", "model": req["model"], "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage})

    return Handler


def start(mode="oracle"):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(mode))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
