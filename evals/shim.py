#!/usr/bin/env python3
"""sakura-shim, graded against a fake model server that replays exactly the mangled replies small models write: the
shim sits between, and what comes out the other side is compared with the call that was meant. Streamed and not.

  evals/shim.py              every case
  evals/shim.py --only NAME  one of: repairs refusals stream proxy
No model, no network beyond 127.0.0.1.
"""

import argparse
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
SHIM = os.path.join(BIN, "sakura-shim")
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "exec_command",
            "parameters": {
                "type": "object",
                "required": ["cmd"],
                "properties": {
                    "cmd": {"type": "string"},
                    "workdir": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "parameters": {
                "type": "object",
                "required": ["patch"],
                "properties": {"patch": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tools",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
REPLIES = {}  # key → ("json", message dict, finish) or ("sse", [chunk dicts or raw], delay)


class Upstream(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *_):
        pass

    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Upstream.seen.append((self.path, req))
        kind, payload, extra = REPLIES[req["messages"][-1]["content"]]
        if kind == "json":
            body = json.dumps(
                {
                    "id": "c1",
                    "object": "chat.completion",
                    "model": "fake",
                    "choices": [
                        {"index": 0, "message": payload, "finish_reason": extra}
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for ch in payload:
            self.wfile.write(
                b"data: "
                + (ch if isinstance(ch, bytes) else json.dumps(ch).encode())
                + b"\n\n"
            )
            self.wfile.flush()
            time.sleep(extra)
        self.wfile.write(b"data: [DONE]\n\n")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Rig:
    def __enter__(self):
        self.tmp = tempfile.mkdtemp()
        self.up = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=self.up.serve_forever, daemon=True).start()
        self.port = free_port()
        self.env = dict(os.environ, SAKURA_HOME=self.tmp)
        self.proc = subprocess.Popen(
            [
                SHIM,
                "run",
                "--port",
                str(self.port),
                "--upstream",
                f"http://127.0.0.1:{self.up.server_port}/v1",
            ],
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        return self

    def __exit__(self, *_):
        self.proc.terminate()
        self.up.shutdown()

    def ask(self, key, stream=False, tools=TOOLS):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        body = {
            "model": "fake",
            "stream": stream,
            "messages": [{"role": "user", "content": key}],
        }
        if tools:
            body["tools"] = tools
        c.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(body),
            {"Content-Type": "application/json"},
        )
        r = c.getresponse()
        if not stream:
            d = json.loads(r.read())
            ch = d["choices"][0]
            return ch["message"], ch["finish_reason"]
        events, times, t0 = [], [], time.time()
        while True:
            line = r.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
                events.append(json.loads(line[5:]))
                times.append(time.time() - t0)
        return events, times

    def log(self):
        try:
            return [json.loads(x) for x in open(os.path.join(self.tmp, "shim.log"))]
        except OSError:
            return []


def call_of(msg):
    """[(name, args dict)] of a message's tool calls; args that aren't valid JSON come back as the raw string."""
    out = []
    for c in msg.get("tool_calls") or []:
        try:
            out.append((c["function"]["name"], json.loads(c["function"]["arguments"])))
        except ValueError:
            out.append((c["function"]["name"], c["function"]["arguments"]))
    return out


def text(content, finish="stop"):
    return ("json", {"role": "assistant", "content": content}, finish)


LS = [("exec_command", {"cmd": "ls -la"})]


def repairs(_):
    cases = {
        "a tool_call tag with a trailing comma": (
            '<tool_call>\n{"name": "exec_command", "arguments": {"cmd": "ls -la",}}\n</tool_call>',
            LS,
        ),
        "a tool_call tag that never closes": (
            '<tool_call>{"name": "exec_command", "arguments": {"cmd": "ls -la"}}',
            LS,
        ),
        "single quotes, the Python way": (
            "<tool_call>{'name': 'exec_command', 'arguments': {'cmd': 'ls -la'}}</tool_call>",
            LS,
        ),
        "arguments as a JSON string inside the JSON": (
            '<tool_call>{"name": "exec_command", "arguments": "{\\"cmd\\": \\"ls -la\\"}"}</tool_call>',
            LS,
        ),
        "a json code block and nothing else": (
            '```json\n{"name": "exec_command", "arguments": {"cmd": "ls -la"}}\n```',
            LS,
        ),
        "a bare object with parameters instead of arguments": (
            '{"name": "exec_command", "parameters": {"cmd": "ls -la"}}',
            LS,
        ),
        "the function= tag": (
            '<function=exec_command>{"cmd": "ls -la"}</function>',
            LS,
        ),
        "TOOL_CALLS and a list": (
            '[TOOL_CALLS] [{"name": "exec_command", "arguments": {"cmd": "ls -la"}}]',
            LS,
        ),
        "the sentence shape": ("[tool_call: exec_command for 'ls -la']", LS),
        "the sentence shape with a named parameter": (
            "[tool_call: exec_command for cmd 'ls -la' with workdir '/srv/app']",
            [("exec_command", {"cmd": "ls -la", "workdir": "/srv/app"})],
        ),
        "a raw newline inside the command": (
            '<tool_call>{"name": "exec_command", "arguments": {"cmd": "echo one\necho two"}}</tool_call>',
            [("exec_command", {"cmd": "echo one\necho two"})],
        ),
        "missing closing braces": (
            '<tool_call>{"name": "exec_command", "arguments": {"cmd": "ls -la"}',
            LS,
        ),
        "a wrong-case name": (
            '<tool_call>{"name": "Exec_Command", "arguments": {"cmd": "ls -la"}}</tool_call>',
            LS,
        ),
        "a namespaced name": (
            '<tool_call>{"name": "functions.exec_command", "arguments": {"cmd": "ls -la"}}</tool_call>',
            LS,
        ),
        "two calls in one reply": (
            '<tool_call>{"name": "exec_command", "arguments": {"cmd": "ls -la"}}</tool_call>\n<tool_call>{"name": "exec_command", "arguments": {"cmd": "pwd"}}</tool_call>',
            LS + [("exec_command", {"cmd": "pwd"})],
        ),
        "a tool that takes nothing": (
            '<tool_call>{"name": "list_tools"}</tool_call>',
            [("list_tools", {})],
        ),
        "a patch with quotes and newlines in it": (
            '<tool_call>{"name": "apply_patch", "arguments": {"patch": "*** Begin Patch\\n+print(\\"hi, {name}\\")\\n*** End Patch"}}</tool_call>',
            [
                (
                    "apply_patch",
                    {"patch": '*** Begin Patch\n+print("hi, {name}")\n*** End Patch'},
                )
            ],
        ),
    }
    out = {}
    with Rig() as rig:
        for name, (content, want) in cases.items():
            REPLIES[name] = text(content)
            msg, finish = rig.ask(name)
            out[f"{name} becomes the call"] = (
                call_of(msg) == want
                and finish == "tool_calls"
                and not msg.get("content")
            )
        REPLIES["prose first"] = text(
            'I\'ll list the files.\n<tool_call>{"name": "exec_command", "arguments": {"cmd": "ls -la"}}</tool_call>'
        )
        msg, finish = rig.ask("prose first")
        out["what was said before the call is kept as the message"] = (
            call_of(msg) == LS and msg["content"] == "I'll list the files."
        )
        REPLIES["bad args"] = (
            "json",
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_7",
                        "type": "function",
                        "function": {
                            "name": "exec_command",
                            "arguments": "{'cmd': 'ls -la',}",
                        },
                    }
                ],
            },
            "tool_calls",
        )
        msg, finish = rig.ask("bad args")
        out["a proper call with broken arguments is mended, its id kept"] = (
            call_of(msg) == LS and msg["tool_calls"][0]["id"] == "call_7"
        )
        REPLIES["good"] = (
            "json",
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_8",
                        "type": "function",
                        "function": {
                            "name": "exec_command",
                            "arguments": '{"cmd":   "ls -la"}',
                        },
                    }
                ],
            },
            "tool_calls",
        )
        msg, _ = rig.ask("good")
        out["a call that was already right is passed on byte for byte"] = (
            msg["tool_calls"][0]["function"]["arguments"] == '{"cmd":   "ls -la"}'
        )
        log = rig.log()
        out["the log says what kind and which tool, and never the command"] = (
            len(log) == len(cases) + 2
            and all(set(e) == {"t", "kind", "tools"} for e in log)
            and "ls -la" not in open(os.path.join(rig.tmp, "shim.log")).read()
            and {
                "tool_call tag",
                "bare json",
                "function tag",
                "TOOL_CALLS",
                "tool_call sentence",
                "arguments",
            }
            <= {e["kind"] for e in log}
        )
        status = subprocess.run(
            [SHIM, "status"], env=rig.env, capture_output=True, text=True
        ).stdout
        out["status counts them by kind and tool"] = (
            "tool_call tag" in status and "exec_command" in status
        )
    return out


def refusals(_):
    cases = {
        "a tool nobody offered": '<tool_call>{"name": "delete_everything", "arguments": {"path": "/"}}</tool_call>',
        "a required parameter missing": '<tool_call>{"name": "exec_command", "arguments": {"workdir": "/tmp"}}</tool_call>',
        "text that stops inside the command string": '<tool_call>{"name": "exec_command", "arguments": {"cmd": "rm -rf /tmp/build',
        "an explanation that shows the JSON shape": 'To run a command I would send {"name": "exec_command", "arguments": {"cmd": "ls"}} to the tool.',
        "a JSON answer that isn't a call": '{"result": 42, "unit": "ms"}',
        "a code block of ordinary JSON": '```json\n{"users": [{"name": "exec_command"}]}\n```',
        "two tags, one of them invalid": '<tool_call>{"name": "exec_command", "arguments": {"cmd": "ls"}}</tool_call><tool_call>{"name": "nope", "arguments": {}}</tool_call>',
        "plain prose": "The build failed because the lockfile is stale. Run npm ci.",
    }
    out = {}
    with Rig() as rig:
        for name, content in cases.items():
            REPLIES[name] = text(content)
            msg, finish = rig.ask(name)
            out[f"{name} is left as it was"] = (
                not msg.get("tool_calls")
                and msg["content"] == content
                and finish == "stop"
            )
        REPLIES["cut off"] = text(
            '<tool_call>{"name": "exec_command", "arguments": {"cmd": "rm -rf build"}',
            "length",
        )
        msg, finish = rig.ask("cut off")
        out["a reply cut off by the length limit is never completed into a call"] = (
            not msg.get("tool_calls") and finish == "length"
        )
        REPLIES["no tools"] = text(
            '<tool_call>{"name": "exec_command", "arguments": {"cmd": "ls -la"}}</tool_call>'
        )
        msg, _ = rig.ask("no tools", tools=None)
        out["a request that offered no tools is passed through"] = not msg.get(
            "tool_calls"
        )
        out["nothing was logged for any of these"] = rig.log() == []
    return out


def sse(parts, finish="stop", tool_deltas=None):
    chunks = [
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "fake",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ],
        }
    ]
    for p in parts:
        chunks.append(
            {
                "id": "s1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "fake",
                "choices": [
                    {"index": 0, "delta": {"content": p}, "finish_reason": None}
                ],
            }
        )
    for d in tool_deltas or []:
        chunks.append(
            {
                "id": "s1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "fake",
                "choices": [
                    {"index": 0, "delta": {"tool_calls": [d]}, "finish_reason": None}
                ],
            }
        )
    chunks.append(
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "fake",
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
        }
    )
    chunks.append(
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "choices": [],
            "usage": {"total_tokens": 9},
        }
    )
    return chunks


def assemble(events):
    content, calls, finish = "", {}, None
    for e in events:
        for ch in e.get("choices") or []:
            d = ch.get("delta") or {}
            content += d.get("content") or ""
            for tc in d.get("tool_calls") or []:
                slot = calls.setdefault(
                    tc.get("index", 0), {"name": "", "arguments": "", "id": None}
                )
                slot["id"] = tc.get("id") or slot["id"]
                slot["name"] += (tc.get("function") or {}).get("name") or ""
                slot["arguments"] += (tc.get("function") or {}).get("arguments") or ""
            finish = ch.get("finish_reason") or finish
    parsed = []
    for _, c in sorted(calls.items()):
        try:
            parsed.append((c["name"], json.loads(c["arguments"])))
        except ValueError:
            parsed.append((c["name"], c["arguments"]))
    return content, parsed, finish


def stream(_):
    out = {}
    with Rig() as rig:
        prose = [
            "The build ",
            "failed because ",
            "the lockfile ",
            "is stale. ",
            "Use < and > carefully, ",
            "[like this].",
        ]
        REPLIES["s prose"] = ("sse", sse(prose), 0.15)
        events, times = rig.ask("s prose", stream=True)
        content, calls, finish = assemble(events)
        first = next(
            t
            for e, t in zip(events, times)
            if (e.get("choices") or [{}])[0].get("delta", {}).get("content")
        )
        out[
            "prose streams through whole, and its first words arrive long before the reply ends"
        ] = (
            content == "".join(prose)
            and not calls
            and finish == "stop"
            and first < times[-1] - 0.5
        )
        out["the usage record at the end still arrives"] = any(
            e.get("usage") == {"total_tokens": 9} for e in events
        )
        tag = [
            "<tool",
            '_call>\n{"name": "exec_',
            'command", "arguments": {"cmd": ',
            '"ls -la",}}\n</tool',
            "_call>",
        ]
        REPLIES["s tag"] = ("sse", sse(tag), 0.02)
        content, calls, finish = assemble(rig.ask("s tag", stream=True)[0])
        out[
            "a tool_call tag split across chunks becomes the call, and none of it leaks as text"
        ] = calls == LS and content == "" and finish == "tool_calls"
        REPLIES["s both"] = (
            "sse",
            sse(
                [
                    "I'll list ",
                    "the files.\n",
                    "<tool_call>",
                    '{"name": "exec_command", "arguments": {"cmd": "ls -la"}}',
                    "</tool_call>",
                ]
            ),
            0.02,
        )
        content, calls, finish = assemble(rig.ask("s both", stream=True)[0])
        out["prose, then a call: the prose is shown and the call is made"] = (
            calls == LS
            and content.strip() == "I'll list the files."
            and finish == "tool_calls"
        )
        REPLIES["s fence"] = (
            "sse",
            sse(
                [
                    "```json\n",
                    '{"name": "exec_command",',
                    ' "arguments": {"cmd": "ls -la"}}',
                    "\n```",
                ]
            ),
            0.02,
        )
        content, calls, finish = assemble(rig.ask("s fence", stream=True)[0])
        out["a streamed json block that is a call becomes one"] = (
            calls == LS and content == ""
        )
        code = ["```python\n", "print('hi')\n", "```\n", "That prints hi."]
        REPLIES["s code"] = ("sse", sse(code), 0.02)
        content, calls, finish = assemble(rig.ask("s code", stream=True)[0])
        out["a streamed code block that isn't a call arrives complete"] = (
            content == "".join(code) and not calls and finish == "stop"
        )
        almost = ["Use the <tool", "box> element, or <function", "ality> tags."]
        REPLIES["s almost"] = ("sse", sse(almost), 0.02)
        content, calls, finish = assemble(rig.ask("s almost", stream=True)[0])
        out[
            "text that only starts like a tag is held a moment, then sent unchanged"
        ] = content == "".join(almost) and not calls
        REPLIES["s bad"] = (
            "sse",
            sse(['<tool_call>{"name": "nope", "arguments": {}}</tool_call>']),
            0.02,
        )
        content, calls, finish = assemble(rig.ask("s bad", stream=True)[0])
        out["a streamed call to a tool nobody offered comes out as the text it was"] = (
            content == '<tool_call>{"name": "nope", "arguments": {}}</tool_call>'
            and not calls
            and finish == "stop"
        )
        REPLIES["s cut"] = (
            "sse",
            sse(
                [
                    '<tool_call>{"name": "exec_command", "arguments": {"cmd": "rm -rf build"}'
                ],
                finish="length",
            ),
            0.02,
        )
        content, calls, finish = assemble(rig.ask("s cut", stream=True)[0])
        out["a streamed reply cut off by length is not completed"] = (
            not calls and finish == "length" and "rm -rf build" in content
        )
        deltas = [
            {
                "index": 0,
                "id": "call_9",
                "type": "function",
                "function": {"name": "exec_command", "arguments": ""},
            },
            {"index": 0, "function": {"arguments": "{'cmd': "}},
            {"index": 0, "function": {"arguments": "'ls -la',}"}},
        ]
        REPLIES["s args"] = (
            "sse",
            sse([], finish="tool_calls", tool_deltas=deltas),
            0.02,
        )
        events, _ = rig.ask("s args", stream=True)
        content, calls, finish = assemble(events)
        out["streamed call deltas with broken arguments are mended, id kept"] = (
            calls == LS
            and finish == "tool_calls"
            and any(
                tc.get("id") == "call_9"
                for e in events
                for ch in e.get("choices") or []
                for tc in (ch.get("delta") or {}).get("tool_calls") or []
            )
        )
        good = [
            {
                "index": 0,
                "id": "call_a",
                "type": "function",
                "function": {"name": "exec_command", "arguments": ""},
            },
            {"index": 0, "function": {"arguments": '{"cmd": "ls'}},
            {"index": 0, "function": {"arguments": ' -la"}'}},
        ]
        REPLIES["s good"] = (
            "sse",
            sse([], finish="tool_calls", tool_deltas=good),
            0.02,
        )
        content, calls, finish = assemble(rig.ask("s good", stream=True)[0])
        out["streamed call deltas that were right arrive as the same call"] = (
            calls == LS and finish == "tool_calls"
        )
    return out


def proxy(tmp):
    out = {}
    with Rig() as rig:
        c = http.client.HTTPConnection("127.0.0.1", rig.port, timeout=10)
        c.request("GET", "/v1/models")
        out["other paths are passed to the model server untouched"] = json.loads(
            c.getresponse().read()
        ) == {"data": [{"id": "fake-model"}]}
        REPLIES["path"] = text("ok")
        Upstream.seen.clear()
        rig.ask("path")
        out["the request reaches the same path with its body intact"] = (
            Upstream.seen
            and Upstream.seen[0][0] == "/v1/chat/completions"
            and Upstream.seen[0][1]["tools"] == TOOLS
        )
        listening = subprocess.run(
            [
                "bash",
                "-c",
                f"cat /proc/net/tcp 2>/dev/null | awk '{{print $2}}'; ss -ltnH 2>/dev/null | awk '{{print $4}}'",
            ],
            capture_output=True,
            text=True,
        ).stdout
        hexport = f"{rig.port:04X}"
        addrs = [
            l
            for l in listening.split()
            if l.upper().endswith(":" + hexport) or l.endswith(f":{rig.port}")
        ]
        outside = socket.socket()
        outside.settimeout(1)
        try:
            host_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            host_ip = "127.0.0.1"
        reachable = False
        if not host_ip.startswith("127."):
            try:
                outside.connect((host_ip, rig.port))
                reachable = True
            except OSError:
                pass
        out["it listens on 127.0.0.1 only"] = (
            bool(addrs)
            and all(
                a.upper().startswith("0100007F:") or a.startswith("127.0.0.1:")
                for a in addrs
            )
            and not reachable
        )
    # the model server is down: say so, in JSON the engine can show
    env = dict(os.environ, SAKURA_HOME=tmp)
    port, dead = free_port(), free_port()
    p = subprocess.Popen(
        [SHIM, "run", "--port", str(port), "--upstream", f"http://127.0.0.1:{dead}"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(
                {"messages": [{"role": "user", "content": "x"}], "tools": TOOLS}
            ),
            {"Content-Type": "application/json"},
        )
        r = c.getresponse()
        body = json.loads(r.read())
        out[
            "a model server that's down is a 502 that says which server and how to take the shim out"
        ] = (
            r.status == 502
            and str(dead) in body["error"]["message"]
            and "sakura-shim off" in body["error"]["message"]
        )
    finally:
        p.terminate()
    # on / ensure / off: the switch, a background start that is reused, and a stop
    eport = free_port()
    env2 = dict(env, SAKURA_SHIM_PORT=str(eport))
    on = subprocess.run([SHIM, "on"], env=env2, capture_output=True, text=True)
    e1 = subprocess.run(
        [SHIM, "ensure", "--upstream", "http://127.0.0.1:9/v1"],
        env=env2,
        capture_output=True,
        text=True,
    )
    pid1 = (
        open(os.path.join(tmp, "shim.pid")).read()
        if os.path.exists(os.path.join(tmp, "shim.pid"))
        else ""
    )
    e2 = subprocess.run(
        [SHIM, "ensure", "--upstream", "http://127.0.0.1:9/v1"],
        env=env2,
        capture_output=True,
        text=True,
    )
    pid2 = (
        open(os.path.join(tmp, "shim.pid")).read()
        if os.path.exists(os.path.join(tmp, "shim.pid"))
        else ""
    )
    e3 = subprocess.run(
        [SHIM, "ensure", "--upstream", "http://127.0.0.1:10/v1"],
        env=env2,
        capture_output=True,
        text=True,
    )
    pid3 = (
        open(os.path.join(tmp, "shim.pid")).read()
        if os.path.exists(os.path.join(tmp, "shim.pid"))
        else ""
    )
    # the ? key with the shim on: the engine is pointed at it, and at the model server when it's off
    fake = os.path.join(tmp, "fakebin")
    os.makedirs(fake)
    with open(os.path.join(fake, "sakura"), "w") as f:
        f.write('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    os.chmod(os.path.join(fake, "sakura"), 0o755)
    lenv = dict(
        env2,
        PATH=fake + os.pathsep + os.environ["PATH"],
        SAKURA_MODEL="x",
        SAKURA_NO_AUTOPULL="1",
        OLLAMA_API_BASE="http://127.0.0.1:10",
    )
    launched = subprocess.run(
        [os.path.join(BIN, "sakura-launch"), "hi"],
        env=lenv,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    ).stdout
    skipped = subprocess.run(
        [os.path.join(BIN, "sakura-launch"), "hi"],
        env=dict(lenv, SAKURA_NO_SHIM="1"),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    ).stdout
    out[
        "with it on, ? points the engine at the shim; SAKURA_NO_SHIM=1 leaves it out for one run"
    ] = (
        f'model_providers.local-ollama.base_url="http://127.0.0.1:{eport}/v1"'
        in launched
        and str(eport) not in skipped
        and "hi" in skipped
    )
    st = subprocess.run(
        [SHIM, "status"], env=env2, capture_output=True, text=True
    ).stdout
    off = subprocess.run([SHIM, "off"], env=env2, capture_output=True, text=True)
    time.sleep(0.3)
    try:
        socket.create_connection(("127.0.0.1", eport), timeout=0.5).close()
        still = True
    except OSError:
        still = False
    out[
        "ensure starts it once, reuses it for the same model server, restarts it for another"
    ] = (
        e1.returncode == 0
        and e2.returncode == 0
        and pid1
        and pid1 == pid2
        and e3.returncode == 0
        and pid3
        and pid3 != pid1
    )
    out["on, status and off agree, and off stops it"] = (
        on.returncode == 0
        and "is on, running" in st
        and off.returncode == 0
        and not still
        and not os.path.exists(os.path.join(tmp, "shim"))
    )
    return out


CASES = {"repairs": repairs, "refusals": refusals, "stream": stream, "proxy": proxy}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    total = passed = 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                results = fn(tmp)
            except Exception as e:
                results = {f"{name} ran without crashing": False}
                print(f"  {name}: {type(e).__name__}: {e}")
        for check, ok in results.items():
            total += 1
            passed += bool(ok)
            print(f"  {'PASS' if ok else 'FAIL'}  {name}: {check}")
    print(f"\n{passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
