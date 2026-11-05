#!/usr/bin/env python3
"""Logging proxy between Sakura and Ollama: see exactly what the model is sent and what it returns.

  python3 evals/trace_proxy.py /path/to/trace.jsonl [port]      # default port 11435
  sakura exec -c 'model_providers.local-ollama.base_url="http://127.0.0.1:11435/v1"' '<prompt>'

Each JSONL line: {"path", "request": <json body>, "response": <raw response text, SSE included>}.

Harness experiments, prototyped here before being ported to Rust (env vars):
  SHIM_NO_THINK=1     send reasoning_effort=none, so answers land in `content` instead of `reasoning`
  SHIM_MOVE_CONTEXT=1 move <lookup>…</lookup> blocks out of the system prompt, onto the latest user message
"""
import http.client
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 11435
UPSTREAM = ("127.0.0.1", int(os.environ.get("TRACE_UPSTREAM_PORT", 11434)))


LOOKUP = re.compile(r"\s*<lookup>.*?</lookup>", re.S)


def shim(body):
    """Apply the enabled experiments to a chat request."""
    try:
        req = json.loads(body)
    except Exception:
        return body
    if not isinstance(req, dict) or not req.get("messages"):
        return body
    if os.environ.get("SHIM_NO_THINK"):
        req["reasoning_effort"] = "none"
    if os.environ.get("SHIM_MOVE_CONTEXT"):
        msgs = req["messages"]
        system = msgs[0].get("content")
        if msgs[0].get("role") == "system" and isinstance(system, str):
            found = [m.group(0).strip() for m in LOOKUP.finditer(system)]
            msgs[0]["content"] = LOOKUP.sub("", system)
            users = [m for m in msgs if m.get("role") == "user"]
            if found and users and isinstance(users[-1].get("content"), str):
                users[-1]["content"] = found[-1] + "\n\n" + users[-1]["content"]
    return json.dumps(req).encode()


class Proxy(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _forward(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = shim(body) if body else body
        conn = http.client.HTTPConnection(*UPSTREAM, timeout=600)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "accept-encoding", "content-length")}
        conn.request(self.command, self.path, body=body or None, headers=headers)
        r = conn.getresponse()
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in ("transfer-encoding", "content-length", "connection"):
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        raw = b""
        while True:
            chunk = r.read1(65536)
            if not chunk:
                break
            raw += chunk
            self.wfile.write(chunk)
            self.wfile.flush()
        try:
            req = json.loads(body) if body else None
        except Exception:
            req = body.decode("utf-8", "replace")
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "request": req, "response": raw.decode("utf-8", "replace")}) + "\n")

    do_GET = do_POST = _forward


ThreadingHTTPServer(("127.0.0.1", PORT), Proxy).serve_forever()
