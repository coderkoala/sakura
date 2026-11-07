#!/usr/bin/env python3
"""Does ?undo put back everything a turn changed, by whatever route, and does ?undo again redo it? Graded by hashing
every file before Sakura, after it, after the undo and after the redo, never by what the model says.

  evals/undo.py                 every case
  evals/undo.py --only NAME
Needs the driver (sakura-launch brings it up). Undo history goes to a temporary XDG_STATE_HOME, not yours.
"""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile


def write(d, files):
    for name, text in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


def tree(*roots):
    """{path: sha256} for every file under the roots (a root may be a single file)."""
    out = {}
    for root in roots:
        if os.path.isfile(root):
            out[root] = hashlib.sha256(open(root, "rb").read()).hexdigest()
            continue
        for base, dirs, files in os.walk(root):
            for n in files:
                p = os.path.join(base, n)
                out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def sakura(d, prompt, env, timeout=900):
    r = subprocess.run(["sakura-launch", "--exec", "--json", "--skip-git-repo-check", prompt], cwd=d, env=env,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    commands = []
    for line in r.stdout.splitlines():
        try:
            item = json.loads(line).get("item", {})
        except ValueError:
            continue
        if item.get("type") == "command_execution":
            commands.append(item.get("command", ""))
    print("  ran:", " | ".join(c[-80:] for c in commands)[-700:])
    return commands


def undo(env, d):
    r = subprocess.run(["sakura-undo", "--yes"], cwd=d, env=env, capture_output=True, text=True, timeout=120)
    print("  undo:", (r.stdout + r.stderr).strip().replace("\n", " | ")[-400:])
    return r.returncode


def run_case(d, env, prompt, roots):
    before = tree(*roots)
    sakura(d, prompt, env)
    after = tree(*roots)
    rc = undo(env, d)
    undone = tree(*roots)
    rc2 = undo(env, d)
    redone = tree(*roots)
    return {
        "Sakura changed files (else the case proves nothing)": after != before,
        "?undo put every file back exactly": rc == 0 and undone == before,
        "?undo again redid it exactly": rc2 == 0 and redone == after,
    }


def refactor(d, env):
    write(d, {
        "shop/cart.py": "from shop.pricing import compute_total\n\n\ndef checkout(items):\n    return compute_total(items)\n",
        "shop/pricing.py": "def compute_total(items):\n    return sum(i['price'] * i['qty'] for i in items)\n",
        "shop/legacy.py": "# unused since 2024\nOLD = True\n",
        "tests/test_pricing.py": "from shop.pricing import compute_total\n\n\ndef test_total():\n"
                                 "    assert compute_total([{'price': 2, 'qty': 3}]) == 6\n",
        "shop/__init__.py": "",
    })
    return run_case(d, env, "In this project: rename the function compute_total to total_price everywhere it's used, delete "
                            "the unused shop/legacy.py, and add a CHANGELOG.md with one line about the rename.", [d])


def any_route(d, env):
    write(d, {
        "config/app.ini": "[web]\nurl = http://example.com\napi = http://api.example.com\n",
        "config/db.ini": "[db]\nhost = http://db.local\n",
    })
    notes = os.path.join(os.path.dirname(d), "notes.txt")
    write(os.path.dirname(d), {"notes.txt": "todo\n"})
    return run_case(d, env, "Use a single python3 one-liner, not edit_file, to replace every http:// with https:// in "
                            f"config/*.ini. Then append the line 'switched to https' to {notes}.", [d, notes])


CASES = {"refactor": refactor, "any-route": any_route}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    ok = total = 0
    for name, case in CASES.items():
        if args.only and args.only != name:
            continue
        print(f"== {name}")
        with tempfile.TemporaryDirectory() as t:
            work = os.path.join(t, "proj")
            os.mkdir(work)
            env = dict(os.environ, XDG_STATE_HOME=os.path.join(t, "state"))
            try:
                result = case(work, env)
            except subprocess.TimeoutExpired:
                result = {"finished in time": False}
            for check, passed in result.items():
                print(f"  {'ok  ' if passed else 'FAIL'} {check}")
                ok += bool(passed)
                total += 1
    print(f"\nundo: {ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
