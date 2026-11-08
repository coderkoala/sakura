#!/usr/bin/env python3
"""Does sakura-gpu behave, with or without a GPU? These checks read the tool's shape, not the card: the verdict line,
the JSON keys, the model list taken from sakura-model, the Xid table, the command `scale` prints. They pass on a machine
with no NVIDIA card (doctor then reports FAIL lines, which is correct) and never need the driver.

  evals/gpu.py
"""
import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
TOOL = os.path.join(BIN, "sakura-gpu")
failures = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f": {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def run(*args, timeout=90):
    return subprocess.run([TOOL, *args], capture_output=True, text=True, timeout=timeout)


print("sakura-gpu doctor")
r = run("doctor")
lines = [l for l in r.stdout.splitlines() if l.strip()]
check("exits 0, 1 or 2", r.returncode in (0, 1, 2), f"exit {r.returncode}: {r.stderr[-300:]}")
check("prints a verdict line first", bool(lines) and any(lines[0].startswith(v) for v in ("HEALTHY", "OK with", "NEEDS YOU", "REBOOT NEEDED")), lines[:1])
check("every finding is tagged", all(l.lstrip().startswith("[") for l in lines[1:]), [l for l in lines[1:] if not l.lstrip().startswith("[")][:2])
check("exit code matches the verdict", (r.returncode == 2) == lines[0].startswith("REBOOT") and (r.returncode == 1) == lines[0].startswith("NEEDS"))

print("sakura-gpu doctor --json")
r = run("doctor", "--json")
try:
    d = json.loads(r.stdout)
except ValueError:
    d = None
check("parses as JSON", d is not None, r.stdout[:200])
if d:
    want = {"verdict", "exit", "findings", "xids", "reboot_xids", "holders", "throttle", "temperature_c", "vram_total_mib", "vram_used_mib"}
    check("has the expected keys", want <= set(d), sorted(want - set(d)))
    check("findings carry level and text", all({"level", "text"} <= set(f) and f["level"] in ("ok", "warn", "fail", "reboot") for f in d["findings"]))
    check("json exit equals the process exit", d["exit"] == r.returncode)

print("sakura-gpu free --json")
r = run("free", "--json")
try:
    d = json.loads(r.stdout)
except ValueError:
    d = None
check("parses as JSON", d is not None, r.stdout[:200])
if d:
    check("has free/total or an error", {"free_mib", "total_mib", "holders"} <= set(d) or "error" in d, sorted(d))

print("sakura-gpu fit")
sm = SourceFileLoader("sakura_model", os.path.join(BIN, "sakura-model")).load_module()
names = [n for n, *_ in sm.ollama_models()]
r = run("fit", "9")
check("runs", r.returncode == 0, r.stderr[-300:])
check("lists every model from sakura-model", all(n in r.stdout for n in names), [n for n in names if n not in r.stdout])
check("lists the driver file", sm.FILENAME in r.stdout)
check("answers the SIZE_GIB question", "a 9 GiB model needs" in r.stdout)
r = run("fit", "--json")
try:
    d = json.loads(r.stdout)
except ValueError:
    d = None
check("--json parses with models and driver", d is not None and {"models", "driver", "vram_free_mib", "ram_gib"} <= set(d), r.stdout[:200])
if d:
    check("json models match sakura-model", [m["model"] for m in d["models"]] == names)
    check("driver cache uses plan()'s arithmetic", d["driver"]["cache_mib"] == 0 or d["driver"]["cache_mib"] <= sm.MAX_CACHE_MIB)

print("Xid table")
gpu = SourceFileLoader("sakura_gpu", TOOL).load_module()
for code in ("13", "31", "43", "45", "61", "62", "69", "79", "109", "119", "120", "154"):
    check(f"knows Xid {code}", code in gpu.XIDS)
check("120 and 154 mean a reboot", gpu.XIDS["120"][1] and gpu.XIDS["154"][1])
check("sakura-model's BAD_XIDS all mean a reboot here", all(gpu.XIDS.get(x, ("", False))[1] for x in sm.BAD_XIDS), sorted(sm.BAD_XIDS))
# the reboot wording lives in doctor(), which only reaches it with a faulty card; read the source for it
src = open(TOOL).read()
check("doctor's Xid finding says reboot", "A reboot is the fix" in src and '"reboot"' in src)

print("sakura-gpu scale")
r = run("scale")
check("runs", r.returncode == 0, r.stderr[-300:])
check("prints a sakura-model command", any(l.strip().startswith("run: sakura-model") for l in r.stdout.splitlines()), r.stdout[-300:])
check("gives a direction", any(w in r.stdout for w in ("RUN the driver", "FALL BACK", "DOWN:")), r.stdout[:200])

print("sakura-gpu reset")
r = run("reset")
check("refuses without --yes", r.returncode == 2 and "--yes" in r.stderr)
r = run("nonsense")
check("unknown command prints usage, exit 2", r.returncode == 2 and "sakura-gpu doctor" in r.stdout)

print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
