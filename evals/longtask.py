#!/usr/bin/env python3
"""A long task that fills the context with command output. Does it still finish, right, and how much compaction does it cost?

  evals/longtask.py [--model M --base-url URL] [--repeat N]

Grades the answer, which needs facts spread over every file, against what's on disk. Reports compactions from the session log.
"""
import argparse
import glob
import json
import os
import random
import re
import subprocess
import tempfile
import time

FILES = 12
LINES = 260  # about 12 KB each, close to the per-output limit


def build(d, rng):
    codes = {}
    for i in range(1, FILES + 1):
        code = rng.randint(100, 999)
        codes[i] = code
        rows = [f"2026-11-0{1 + j % 9} 10:{j % 60:02d}:00 INFO worker-{j % 7} handled request {rng.randint(10000, 99999)} in {rng.randint(1, 900)}ms" for j in range(LINES)]
        rows[rng.randint(40, LINES - 40)] = f"2026-11-05 10:00:00 NOTICE shard-{i} checksum code is {code}"
        with open(os.path.join(d, f"shard-{i:02d}.log"), "w") as f:
            f.write("\n".join(rows) + "\n")
    return codes


def run(args, rng):
    with tempfile.TemporaryDirectory(prefix="sakura-long-") as d:
        codes = build(d, rng)
        prompt = (f"There are {FILES} logs here, shard-01.log to shard-{FILES:02d}.log. Read each one in full with cat, one command per file, in order, "
                  "without grep. Each has one NOTICE line with a checksum code. Then tell me the code of every shard and their total.")
        env = dict(os.environ, SAKURA_MEMORY_DIR=os.path.join(d, ".m"), SAKURA_TOOLS_DIR=os.path.join(d, ".t"))
        cmd = ["sakura", "exec", "--dangerously-bypass-hook-trust", "--skip-git-repo-check", "--json", "-m", args.model]
        if args.base_url:
            cmd += ["-c", f'model_providers.local-ollama.base_url="{args.base_url}"']
            env["SAKURA_ROUTER_URL"] = args.base_url
        t0 = time.time()
        try:
            out = subprocess.run(cmd + [prompt], cwd=d, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=args.timeout).stdout
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        took = time.time() - t0
    final, cats, session, tokens = "", 0, None, []
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        session = session or ev.get("thread_id")
        item = ev.get("item", {})
        if ev.get("type") == "turn.completed":
            tokens.append(ev.get("usage", {}).get("input_tokens", 0))
        if ev.get("type") == "item.completed":
            if item.get("type") == "agent_message" and item.get("text"):
                final = item["text"]
            if item.get("type") == "command_execution" and "shard-" in (item.get("command") or ""):
                cats += 1
    compactions = 0
    if session:
        for path in glob.glob(os.path.expanduser(f"~/.sakura/sessions/**/*{session}*.jsonl"), recursive=True):
            compactions = sum(json.loads(l).get("type") == "compacted" for l in open(path))
    found = sum(str(c) in final for c in codes.values())
    total = str(sum(codes.values()))
    ok = found == FILES and bool(re.search(r"\b" + total + r"\b", final.replace(",", "")))
    print(f"{'PASS' if ok else 'FAIL'} {took:.0f}s, {cats} reads, {compactions} compactions, {found}/{FILES} codes, total {'right' if total in final.replace(',', '') else 'wrong'}, input tokens {tokens}", flush=True)
    print("  ", final[:200].replace("\n", " "), flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen36-q3")
    ap.add_argument("--base-url", default="http://127.0.0.1:8091/v1")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    rng = random.Random()
    passed = sum(run(a, rng) for _ in range(a.repeat))
    print(f"{passed}/{a.repeat}")


if __name__ == "__main__":
    main()
