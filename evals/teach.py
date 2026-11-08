#!/usr/bin/env python3
"""Does ?teach turn what the user just did into a kept tool that works? Graded by sakura-tool's own gate (the tool exists
and its check passes in a clean directory) and by running the tool on known input, never by what the session says.

  evals/teach.py                 every case
  evals/teach.py --only NAME
Needs the driver (sakura-launch brings it up).
"""
import argparse
import json
import os
import subprocess
import tempfile


def teach(d, history, words, tools, timeout=900):
    hist = os.path.join(d, "..", "history")
    with open(hist, "w") as f:
        f.write(history)
    env = dict(os.environ, SAKURA_TOOLS_DIR=tools)
    env.pop("SAKURA_COORDINATOR", None)
    r = subprocess.run(["sakura-teach", "--exec", "--json", "--history", hist, *words], cwd=d, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    commands, answer = [], ""
    for line in r.stdout.splitlines():
        try:
            item = json.loads(line).get("item", {})
        except ValueError:
            continue
        if item.get("type") == "command_execution":
            commands.append(item.get("command", ""))
        elif item.get("type") == "agent_message":
            answer = item.get("text", "")
    print("  ran:", " | ".join(c[-80:] for c in commands)[-700:])
    print("  said:", answer[-500:].replace("\n", " "))
    return commands, answer


def kept(tools):
    env = dict(os.environ, SAKURA_TOOLS_DIR=tools)
    names = [l.split(":")[0].strip() for l in subprocess.run(["sakura-tool", "list"], env=env, capture_output=True, text=True).stdout.splitlines() if ":" in l]
    check = subprocess.run(["sakura-tool", "check"], env=env, capture_output=True, text=True)
    print("  kept:", names, "| check:", check.stdout.strip().replace("\n", " ")[-300:])
    return names, check.returncode == 0 and bool(names)


def run_tool(tools, name, stdin, *args):
    env = dict(os.environ, PATH=os.environ["PATH"] + os.pathsep + os.path.join(tools, "bin"))
    r = subprocess.run([name, *args], env=env, input=stdin, capture_output=True, text=True, timeout=60)
    return r.stdout


def column_count(d, tools):
    with open(os.path.join(d, "orders.csv"), "w") as f:
        f.write("id,city,amount\n1,Kathmandu,10\n2,Pokhara,5\n3,Kathmandu,7\n4,Lalitpur,1\n5,Kathmandu,2\n")
    history = ("cut -d, -f2 orders.csv | tail -n +2 | sort | uniq -c | sort -rn\n"
               "cut -d, -f2 orders.csv | tail -n +2 | sort | uniq -c | sort -rn | head -3\n")
    teach(d, history, ["a tool that counts the values of a named CSV column, most common first, so I can use it on any file"], tools)
    names, ok = kept(tools)
    out = ""
    if names:
        for args in (("city",), ("orders.csv", "city"), ("city", "orders.csv")):
            try:
                out = run_tool(tools, names[0], open(os.path.join(d, "orders.csv")).read(), *args)
            except (OSError, subprocess.SubprocessError):
                out = ""
            if "Kathmandu" in out:
                break
    first = next((l for l in out.splitlines() if l.strip()), "")
    return {
        "a tool was kept and its check passes": ok,
        "the tool counts the right column": "Kathmandu" in out and "3" in first and "Kathmandu" in first,
        "the tool has no hard-coded file name": not any("orders.csv" in open(os.path.join(tools, "bin", n), errors="replace").read() for n in names),
    }


CASES = {"column-count": column_count}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    passed = total = 0
    for name, case in CASES.items():
        if args.only and args.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            work, tools = os.path.join(tmp, "work"), os.path.join(tmp, "tools")
            os.mkdir(work)
            print(f"\n== {name}", flush=True)
            for check, ok in case(work, tools).items():
                print(f"  {'ok  ' if ok else 'FAIL'} {check}", flush=True)
                total += 1
                passed += bool(ok)
    print(f"\nteach: {passed}/{total}")


if __name__ == "__main__":
    main()
