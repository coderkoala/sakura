#!/usr/bin/env python3
"""Speed and tool-call probe for an OpenAI-compatible model server.

  python3 evals/bench_server.py http://127.0.0.1:8091/v1 <model name>

Reports write and read speed on short and long prompts, and whether tool calls come back as real
structured calls (the requirement for driving a Sakura session). Timings use the server's own figures
when it reports them (llama-server), else wall time.
"""
import json
import sys
import time
import urllib.request

BASE, MODEL = sys.argv[1].rstrip("/"), sys.argv[2]


def chat(messages, max_tokens=200, tools=None):
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "stream": False,
            "reasoning_effort": "none", "temperature": 0}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    data = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return data, time.time() - t


def report(label, data, wall):
    tm = data.get("timings") or {}
    usage = data.get("usage") or {}
    write = tm.get("predicted_per_second") or usage.get("completion_tokens", 0) / max(wall, 0.01)
    read = tm.get("prompt_per_second") or 0
    print(f"{label:22s} write {write:6.1f} tok/s   read {read:7.0f} tok/s   "
          f"prompt {usage.get('prompt_tokens', '?')} tok   wall {wall:.1f}s")


question = [{"role": "user", "content": "Explain in about 200 words how a B-tree index speeds up lookups."}]
data, wall = chat(question, 300)
report("short, cold", data, wall)
print("  sample:", (data["choices"][0]["message"].get("content") or "")[:100].replace("\n", " "))
data, wall = chat(question, 300)
report("short, warm", data, wall)

filler = " ".join(f"Line {i}: the quick brown fox jumps over the lazy dog near riverbank number {i}." for i in range(1100))
data, wall = chat([{"role": "user", "content": filler + "\n\nIn one sentence: what animal jumps?"}], 120)
report("long prompt", data, wall)
print("  sample:", (data["choices"][0]["message"].get("content") or "")[:100].replace("\n", " "))

tools = [{"type": "function", "function": {
    "name": "exec_command", "description": "Run a shell command",
    "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}}]
good = 0
prompts = ["run: uname -r", "list the files here", "show free disk space", "what's my kernel version? use the tool"]
for prompt in prompts:
    data, wall = chat([{"role": "user", "content": prompt}], 120, tools)
    msg = data["choices"][0]["message"]
    calls = msg.get("tool_calls")
    good += bool(calls)
    shown = f"{calls[0]['function']['name']} {calls[0]['function']['arguments']}" if calls else f"NO CALL: {str(msg.get('content'))[:70]}"
    print(f"  tool {prompt!r}: {shown} ({wall:.1f}s)")
print(f"real tool calls: {good}/{len(prompts)}")
