#!/usr/bin/env python3
"""Does sakura-backup make, prove and prune real restic backups? Deterministic, against a temp source tree and a
temp local repo; needs restic (skips with a note when it's absent). Checks: init writes a 0600 password file and
refuses a duplicate name; run snapshots the sources; prove restores a real file whose bytes match, runs restic
check, and leaves a restored timestamp in the guardian's config; a changed file makes a second snapshot; restore
--to lands the new bytes; a second prove passes; forget --keep-last 1 prunes to one snapshot; a missing source
fails the run; the password never appears in any command's output.

  evals/backup.py
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "sakura-backup")
OUTPUTS = []  # (argv, stdout+stderr) of every run, for the password grep


def run(args, env, timeout=300):
    r = subprocess.run([sys.executable, TOOL, *args], env=env, capture_output=True, text=True, timeout=timeout)
    OUTPUTS.append((args, r.stdout + r.stderr))
    return r


def main():
    if not shutil.which("restic"):
        print("backup: SKIP — restic isn't installed (sudo -A apt-get install -y restic); nothing graded")
        return 0
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok)))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail and not ok else ""), flush=True)

    with tempfile.TemporaryDirectory(prefix="sakura-backup-eval-") as tmp:
        src = os.path.join(tmp, "src")
        os.makedirs(os.path.join(src, "sub"))
        files = {"notes.txt": b"the quick brown fox\n" * 40,
                 "sub/data.bin": bytes(range(256)) * 20,
                 "sub/config.ini": b"[main]\nkey = value\n"}
        for rel, body in files.items():
            with open(os.path.join(src, rel), "wb") as f:
                f.write(body)
        env = dict(os.environ)
        env.update({"SAKURA_BACKUP_DIR": os.path.join(tmp, "cfg"), "SAKURA_GUARDIAN_DIR": os.path.join(tmp, "guardian"),
                    "XDG_CACHE_HOME": os.path.join(tmp, "cache")})
        repo = os.path.join(tmp, "repo")

        print("== init", flush=True)
        r = run(["init", "demo", repo, "--source", src], env)
        check("init exits 0", r.returncode == 0, r.stdout + r.stderr)
        check("it says where the password lives", "demo.pass" in r.stdout)
        passfile = os.path.join(tmp, "cfg", "demo.pass")
        password = open(passfile, encoding="utf-8").read().strip() if os.path.exists(passfile) else ""
        check("the password file exists with 32 chars", len(password) == 32)
        check("the password file is 0600", os.path.exists(passfile) and stat.S_IMODE(os.stat(passfile).st_mode) == 0o600)
        conf = json.load(open(os.path.join(tmp, "cfg", "demo.json"))) if os.path.exists(os.path.join(tmp, "cfg", "demo.json")) else {}
        check("the config records v, dest and sources", conf.get("v") == 1 and conf.get("dest") == repo and conf.get("sources") == [src])
        r = run(["init", "demo", os.path.join(tmp, "repo2"), "--source", src], env)
        check("a second init with the same name is refused", r.returncode != 0 and "already exists" in r.stderr)
        check("and it didn't touch the repo config", json.load(open(os.path.join(tmp, "cfg", "demo.json"))).get("dest") == repo)

        print("== run and prove", flush=True)
        r = run(["run", "demo"], env)
        check("run exits 0 and prints a snapshot id", r.returncode == 0 and re.search(r"snapshot [0-9a-f]{8}", r.stdout))
        r = run(["prove", "demo"], env)
        check("prove exits 0", r.returncode == 0, r.stdout + r.stderr)
        named = [rel for rel in files if os.path.basename(rel) in r.stdout]
        check("it names a real restored file", len(named) == 1)
        check("the bytes matched the live file", "bytes match" in r.stdout)
        check("restic check ran clean", "check found no errors" in r.stdout)
        gconf = {}
        try:
            gconf = json.load(open(os.path.join(tmp, "guardian", "config.json")))
        except (OSError, ValueError):
            pass
        restored = gconf.get("backups", {}).get("demo", {}).get("restored")
        check("the guardian got a restored timestamp", isinstance(restored, (int, float)) and restored > 0)
        check("no scratch restore dir was left behind", not [d for d in os.listdir(tempfile.gettempdir()) if d.startswith("sakura-prove-")])

        print("== change, second snapshot, restore", flush=True)
        new_body = b"all new content after the change\n" * 10
        with open(os.path.join(src, "notes.txt"), "wb") as f:
            f.write(new_body)
        r = run(["run", "demo"], env)
        check("a second run succeeds", r.returncode == 0)
        r = run(["snapshots", "demo"], env)
        check("snapshots shows 2", "2 snapshots" in r.stdout, r.stdout)
        out = os.path.join(tmp, "out")
        r = run(["restore", "demo", "--to", out], env)
        check("restore --to exits 0", r.returncode == 0, r.stdout + r.stderr)
        landed = os.path.join(out, src.lstrip(os.sep), "notes.txt")
        check("the changed file came back with its new bytes",
              os.path.isfile(landed) and open(landed, "rb").read() == new_body)
        r = run(["restore", "demo"], env)
        check("restore without --to is refused", r.returncode != 0 and "--to" in r.stderr)
        r = run(["prove", "demo"], env)
        check("a second prove still passes", r.returncode == 0 and "bytes match" in r.stdout, r.stdout + r.stderr)

        print("== forget", flush=True)
        r = run(["forget", "demo", "--keep-last", "1"], env)
        check("forget --keep-last 1 exits 0", r.returncode == 0, r.stdout + r.stderr)
        r = run(["snapshots", "demo"], env)
        check("one snapshot remains", "1 snapshots" in r.stdout, r.stdout)
        r = run(["forget", "demo"], env)
        check("forget without a keep policy is refused", r.returncode != 0 and "keep" in r.stderr)

        print("== a missing source", flush=True)
        gone_src = os.path.join(tmp, "gone-src")
        os.makedirs(gone_src)
        open(os.path.join(gone_src, "x"), "w").write("x")
        r = run(["init", "gone", os.path.join(tmp, "gone-repo"), "--source", gone_src], env)
        check("a second backup inits beside the first", r.returncode == 0)
        shutil.rmtree(gone_src)
        r = run(["run", "gone"], env)
        check("run with a missing source fails nonzero", r.returncode != 0 and "missing" in r.stderr)

        print("== the password stays secret", flush=True)
        leaks = [argv for argv, out in OUTPUTS if password and password in out]
        check("the password never appeared in any command's output", bool(password) and not leaks, str(leaks))
        r = run(["list"], env)
        check("list names both backups without the password", r.returncode == 0 and "demo" in r.stdout
              and "gone" in r.stdout and password not in r.stdout + r.stderr)

    passed = sum(ok for _, ok in checks)
    print(f"\nbackup: {passed}/{len(checks)}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
