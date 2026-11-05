#!/usr/bin/env python3
"""Does the coordinator pattern hold up? Runs sakura-worker and a coordinator session in throwaway git repos, and grades
by the repo's real state and the worker's exit status, never by what the model says.

  evals/coordinator.py [--only NAME]
"""
import argparse
import json
import os
import subprocess
import tempfile
import time

BUGGY = "def add(a, b):\n    return a - b\n"
PROVE_ADD = "python3 -c 'import calc; assert calc.add(2, 3) == 5'"


def sh(cmd, cwd, env, timeout=1200):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def repo(tmp, env):
    d = tempfile.mkdtemp(prefix="repo-", dir=tmp)
    open(f"{d}/calc.py", "w").write(BUGGY)
    subprocess.run("git init -q -b main . && git config user.email t@t && git config user.name t && git add . && git commit -qm init",
                   shell=True, cwd=d, check=True, env=env)
    return d


def worker_passes(d, env):
    r = sh(["sakura-worker", "--verify", PROVE_ADD, "--scope", "calc.py", "add() in calc.py subtracts. Make it add."], d, env)
    print(r.stdout[-700:])
    return {"exit 0": r.returncode == 0, "says PASSED": "WORKER PASSED" in r.stdout,
            "really fixed": sh(["bash", "-c", PROVE_ADD], d, env).returncode == 0, "calc.py listed": "calc.py" in r.stdout}


def worker_cant_fake_it(d, env):
    # The verify can't pass, whatever the worker says about its work.
    r = sh(["sakura-worker", "--verify", "test -f /nonexistent/never", "Write the word hello to note.txt."], d, env)
    print(r.stdout[-500:])
    return {"exit 1": r.returncode == 1, "says FAILED": "WORKER FAILED" in r.stdout, "retried": "attempt 2/2" in r.stdout}


def worker_stays_in_scope(d, env):
    r = sh(["sakura-worker", "--retries", "0", "--scope", "allowed.txt", "--verify", "true", "Write the word hello to other.txt. This is the whole job."], d, env)
    print(r.stdout[-500:])
    other = os.path.exists(f"{d}/other.txt")
    # Either the worker respected its scope and didn't write it, or it did and the job failed. Both are right.
    return {"breach is caught": (r.returncode == 1 and "outside its scope" in r.stdout) if other else True}


def coordinator(d, env):
    env = dict(env, SAKURA_COORDINATOR="1")
    prompt = ("In this repo, do these in order: 1) add() in calc.py subtracts, fix it. 2) Add a sub(a, b) function to calc.py. "
              "3) Add test_calc.py, runnable with `python3 test_calc.py`, asserting add(2,3)==5 and sub(5,3)==2. "
              "Don't commit. Tell me when it's done and what proved it.")
    t0 = time.time()
    r = sh(["sakura-launch", "--exec", "--skip-git-repo-check", "--json", prompt], d, env, timeout=1500)
    cmds, final = [], ""
    for line in r.stdout.splitlines():
        try:
            item = json.loads(line).get("item", {})
        except ValueError:
            continue
        if item.get("type") == "agent_message" and item.get("text"):
            final = item["text"]
        if item.get("type") == "command_execution" and item.get("command") and item.get("exit_code") is not None:
            cmds.append(item["command"])
    print(f"{time.time() - t0:.0f}s, {len(cmds)} commands by the coordinator:")
    for c in cmds:
        print("  ", c[:140].replace("\n", " "))
    print("final:", final[:400])
    state = subprocess.run(["sakura-memory", "state"], cwd=d, env=env, capture_output=True, text=True).stdout
    print("state tail:", state[-300:])
    return {"tests pass for real": sh(["python3", "test_calc.py"], d, env).returncode == 0 if os.path.exists(f"{d}/test_calc.py") else False,
            "add really fixed": sh(["bash", "-c", PROVE_ADD], d, env).returncode == 0,
            "used a worker": any("sakura-worker" in c for c in cmds),
            "wrote state": "## Log\n-" in state,
            "reported back": bool(final)}


CASES = {"worker-passes": worker_passes, "worker-cant-fake-it": worker_cant_fake_it, "worker-stays-in-scope": worker_stays_in_scope, "coordinator": coordinator}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    passed = total = 0
    with tempfile.TemporaryDirectory(prefix="sakura-coord-") as tmp:
        env = dict(os.environ, SAKURA_MEMORY_DIR=os.path.join(tmp, "mem"))
        for name, fn in CASES.items():
            if args.only and args.only != name:
                continue
            print(f"--- {name}", flush=True)
            checks = fn(repo(tmp, env), env)
            ok = all(checks.values())
            total += 1
            passed += ok
            print(f"{'PASS' if ok else 'FAIL'} {name} {checks}", flush=True)
    print(f"{passed}/{total}")
    raise SystemExit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
