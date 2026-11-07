#!/usr/bin/env python3
"""PreToolUse: snapshot what a command could change before it runs, so `?undo` can put all of it back.

The first time in a turn that a command might write, the directory it runs in is snapshotted: a git tree in a store of
Sakura's own (never the project's .git), so writes by any route are covered, edit_file, sed, python, rm alike. Every
file the command names as a path is saved as well, so a file outside that directory, or one .gitignore hides, comes
back too. `sakura-undo` (the `?undo` key) shows what the last turn changed and puts it back; running it again redoes.

Part of the guard (sakura-guard-install): Sakura can't switch off its own undo. It never blocks a command: any
failure here is logged and the command runs. Limits: a directory over MAX_FILES files or MAX_TOTAL bytes, $HOME and
/ get only the named files; files over MAX_FILE bytes are skipped; nothing outside this machine can be undone.

  python3 undo_snapshot.py --selftest
"""
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "sakura", "undo")
EXCLUDE = ["node_modules/", "vendor/", ".git/", "target/", "__pycache__/", ".venv/", "venv/", ".tox/", ".cache/",
           ".mypy_cache/", ".pytest_cache/", "*.gguf", "*.iso", "*.qcow2"]
PRUNE_DIRS = {e.rstrip("/") for e in EXCLUDE if e.endswith("/")}
MAX_FILES = 20000
MAX_TOTAL = 1 << 30       # 1 GiB in a directory
MAX_FILE = 50 << 20       # 50 MiB a file
KEEP_DAYS = 30
GIT_ENV = {"GIT_AUTHOR_NAME": "sakura-undo", "GIT_AUTHOR_EMAIL": "undo@localhost", "GIT_COMMITTER_NAME": "sakura-undo",
           "GIT_COMMITTER_EMAIL": "undo@localhost", "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

# Commands that only read: no snapshot. Anything else, or any redirect into a file, gets one.
READERS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg", "ag", "ls", "ll", "tree", "stat", "file",
           "wc", "du", "df", "diff", "cmp", "sha256sum", "sha1sum", "md5sum", "echo", "printf", "pwd", "cd", "which", "type",
           "command", "whoami", "id", "date", "uname", "env", "printenv", "ps", "pgrep", "free", "uptime", "hostname",
           "view_file", "fetch_url", "web_search", "wikipedia", "curated_search", "consult", "sakura-recall", "jq", "true",
           "false", "test", "[", "nproc", "lsblk", "ip", "ss", "ping", "dig", "host", "nslookup", "ssh", "realpath",
           "readlink", "basename", "dirname", "column", "sort", "uniq", "cut", "tr", "nl", "bat", "journalctl", "lscpu"}
GIT_READS = {"status", "diff", "log", "show", "blame", "grep", "rev-parse", "ls-files", "describe", "shortlog", "reflog"}


def read_only(cmd):
    if re.search(r"(?<![0-9&])>(?!&|\s*/dev/null)", re.sub(r"[0-9]?>\s*/dev/null|2>&1|>&2", "", cmd)):
        return False
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        try:
            words = shlex.split(seg)
        except ValueError:
            return False
        while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
            words = words[1:]
        if not words:
            continue
        first = os.path.basename(words[0])
        if first == "sudo":
            return False
        if first in READERS:
            continue
        if first == "git" and len(words) > 1 and words[1] in GIT_READS:
            continue
        if first == "sed" and "-n" in words[1:3] and not any(w.startswith("-i") for w in words):
            continue
        if first == "find" and not any(w in ("-delete", "-exec", "-execdir", "-ok", "-fprint", "-fprintf", "-fls") for w in words):
            continue
        if first == "curl" and not any(w in ("-O", "--output", "--remote-name") or w.startswith("-o") for w in words[1:]):
            continue  # it writes only with -o/-O; what it sends elsewhere can't be undone here anyway
        if len(words) == 2 and words[1] in ("--help", "-h", "--version", "-V"):
            continue
        return False
    return True


def _key(text):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:120]


def _git(store, work, *args, input=None):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", f"--git-dir={store}", f"--work-tree={work}", *args], input=input, env=env,
                          capture_output=True, timeout=60, check=True).stdout


def _store_for(d):
    store = os.path.join(STATE, "stores", hashlib.sha1(d.encode()).hexdigest()[:16] + ".git")
    if not os.path.isdir(store):
        os.makedirs(os.path.dirname(store), exist_ok=True)
        subprocess.run(["git", "init", "-q", "--bare", store], check=True, capture_output=True, timeout=30)
        for k, v in (("core.bare", "false"), ("core.autocrlf", "false"), ("core.quotepath", "false")):
            subprocess.run(["git", f"--git-dir={store}", "config", k, v], check=True, capture_output=True)
        with open(os.path.join(store, "where"), "w") as f:
            f.write(d + "\n")
    return store


def eligible(d):
    """(ok, big files to leave out) for snapshotting directory d whole."""
    home = os.path.realpath(os.path.expanduser("~"))
    if d in ("/", home, "/home", "/tmp", "/root", "/usr", "/etc", "/var") or d.startswith(os.path.realpath(STATE)):
        return False, []
    count = total = 0
    big = []
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in PRUNE_DIRS]
        for name in files:
            p = os.path.join(root, name)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            count += 1
            if st.st_size > MAX_FILE:
                big.append(os.path.relpath(p, d))
                continue
            total += st.st_size
            if count > MAX_FILES or total > MAX_TOTAL:
                return False, []
    return True, big


def snapshot_dir(d, label):
    """Commit d's current tree into its store; returns (store, commit) or None."""
    ok, big = eligible(d)
    if not ok:
        return None
    store = _store_for(d)
    os.makedirs(os.path.join(store, "info"), exist_ok=True)
    with open(os.path.join(store, "info", "exclude"), "w") as f:
        f.write("\n".join(EXCLUDE + ["/" + re.sub(r"([\\*?\[])", r"\\\1", b) for b in big]) + "\n")
    with open(os.path.join(store, "lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _git(store, d, "add", "-A", "--ignore-errors", ".")
        tree = _git(store, d, "write-tree").decode().strip()
        commit = _git(store, d, "commit-tree", tree, "-m", label).decode().strip()
        _git(store, d, "update-ref", f"refs/sakura/{_key(label)}", commit)
    return store, commit


def named_paths(cmd, cwd):
    """Paths the command names, as absolute paths: what it may be about to write."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)  # ; & | < > become tokens of their own
        lex.whitespace_split = True
        words = list(lex)
    except ValueError:
        words = cmd.split()
    out = []
    for w in words:
        if not w or w.startswith("-") or set(w) <= set(";&|<>()") or "://" in w or "=" in w.split("/")[0]:
            continue
        if not re.search(r"[/.]", w) and not os.path.exists(os.path.join(cwd, w)):
            continue
        p = os.path.realpath(os.path.join(cwd, os.path.expanduser(w)))
        if p.startswith(os.path.realpath(STATE)) or p.startswith("/proc") or p.startswith("/dev") or p.startswith("/sys"):
            continue
        if os.path.isfile(p) or (not os.path.exists(p) and os.path.isdir(os.path.dirname(p))):
            out.append(p)
    return out


def save_file(p, keydir):
    """A copy of file p as it is now, or a note that it didn't exist."""
    if not os.path.exists(p):
        return {"path": p, "saved": None}
    try:
        st = os.stat(p)
        if st.st_size > MAX_FILE or not os.access(p, os.R_OK):
            return None
        os.makedirs(keydir, exist_ok=True)
        dest = os.path.join(keydir, hashlib.sha1(p.encode()).hexdigest())
        shutil.copy2(p, dest)
        return {"path": p, "saved": dest, "mode": st.st_mode & 0o7777}
    except OSError:
        return None


def _record_path(key):
    return os.path.join(STATE, "turns", key + ".json")


def load(key):
    try:
        with open(_record_path(key)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def store_record(rec):
    os.makedirs(os.path.join(STATE, "turns"), exist_ok=True)
    tmp = _record_path(rec["key"]) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f)
    os.replace(tmp, _record_path(rec["key"]))


def snapshot(cmd, cwd, session, turn):
    """Called before each command. Snapshots the first time in a turn that a directory or file is about to change."""
    if read_only(cmd):
        return None
    key = _key(f"{session}-{turn}" if turn else f"{session}-{int(time.time())}")
    rec = load(key) or {"key": key, "time": time.time(), "session": session, "turn": turn, "dirs": [], "files": [],
                        "commands": [], "undone": False}
    d = os.path.realpath(cwd)
    if d not in [x["dir"] for x in rec["dirs"]] and d not in rec.get("skipped", []):
        snap = snapshot_dir(d, key)
        if snap:
            rec["dirs"].append({"dir": d, "store": snap[0], "commit": snap[1]})
        else:
            rec.setdefault("skipped", []).append(d)
    have = {f["path"] for f in rec["files"]}
    for p in named_paths(cmd, d):
        if p not in have:
            saved = save_file(p, os.path.join(STATE, "files", key))
            if saved:
                rec["files"].append(saved)
                have.add(p)
    rec["commands"].append(cmd[:300])
    store_record(rec)
    if len(rec["commands"]) == 1:
        prune()
    return rec


def prune():
    cutoff = time.time() - KEEP_DAYS * 86400
    for rec in records():
        if rec["time"] < cutoff:
            for e in rec["dirs"]:
                try:
                    _git(e["store"], e["dir"], "update-ref", "-d", f"refs/sakura/{rec['key']}")
                except Exception:
                    pass
            shutil.rmtree(os.path.join(STATE, "files", rec["key"]), ignore_errors=True)
            try:
                os.remove(_record_path(rec["key"]))
            except OSError:
                pass


def records():
    """Every change set, newest first."""
    out = []
    try:
        names = os.listdir(os.path.join(STATE, "turns"))
    except OSError:
        return out
    for n in names:
        if n.endswith(".json"):
            rec = load(n[:-5])
            if rec:
                out.append(rec)
    return sorted(out, key=lambda r: r["time"], reverse=True)


def changes(rec):
    """What happened since the snapshot: [(action, path, how)]; action is restore or remove."""
    out = []
    for e in rec["dirs"]:
        d, store = e["dir"], e["store"]
        if not os.path.isdir(d):
            out.append(("restore", d, ("dir", e)))
            continue
        with open(os.path.join(store, "lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _git(store, d, "add", "-A", "--ignore-errors", ".")
            now = _git(store, d, "write-tree").decode().strip()
        diff = _git(store, d, "diff-tree", "-r", "-z", "--no-renames", "--name-status", e["commit"], now).decode()
        parts = diff.split("\0")
        for status, path in zip(parts[0::2], parts[1::2]):
            if not path:
                continue
            full = os.path.join(d, path)
            out.append(("remove", full, None) if status == "A" else ("restore", full, ("git", e, path)))
    seen = {p for _, p, _ in out}
    for f in rec["files"]:
        p = f["path"]
        if p in seen:
            continue
        if f["saved"] is None:
            if os.path.lexists(p):
                out.append(("remove", p, None))
        elif not os.path.exists(p) or open(p, "rb").read() != open(f["saved"], "rb").read():
            out.append(("restore", p, ("file", f)))
    return out


def undo(rec, todo):
    """Put everything back; first snapshot the present as a change set of its own, so undoing again redoes."""
    redo = {"key": _key(f"undo-{rec['key']}-{int(time.time())}"), "time": time.time(), "session": rec["session"],
            "turn": f"undo of {rec['key']}", "dirs": [], "files": [], "commands": ["sakura-undo"], "undone": False}
    for e in rec["dirs"]:
        if os.path.isdir(e["dir"]):
            snap = snapshot_dir(e["dir"], redo["key"])
            if snap:
                redo["dirs"].append({"dir": e["dir"], "store": snap[0], "commit": snap[1]})
    for f in rec["files"]:
        saved = save_file(f["path"], os.path.join(STATE, "files", redo["key"]))
        if saved:
            redo["files"].append(saved)
    errors = []
    by_store = {}
    for action, path, how in todo:
        try:
            if action == "remove":
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            elif how[0] == "git":
                by_store.setdefault((how[1]["store"], how[1]["dir"], how[1]["commit"]), []).append(how[2])
            elif how[0] == "file":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy2(how[1]["saved"], path)
                os.chmod(path, how[1]["mode"])
            elif how[0] == "dir":
                e = how[1]
                os.makedirs(e["dir"], exist_ok=True)
                by_store.setdefault((e["store"], e["dir"], e["commit"]), []).append(".")
        except OSError as err:
            errors.append(f"{path}: {err.strerror}")
    for (store, d, commit), paths in by_store.items():
        try:
            _git(store, d, "restore", f"--source={commit}", "--worktree", "--pathspec-from-file=-", "--pathspec-file-nul",
                 input="\0".join(paths).encode())
        except subprocess.CalledProcessError as err:
            errors.append(f"{d}: {err.stderr.decode(errors='replace').strip()[:200]}")
    rec["undone"] = True
    store_record(rec)
    store_record(redo)
    return errors


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if os.environ.get("SAKURA_UNDO") == "0":
        return 0
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") not in ("Bash", "shell", "exec_command", "local_shell"):
            return 0
        cmd = (data.get("tool_input") or {}).get("command")
        if isinstance(cmd, list):
            cmd = " ".join(shlex.quote(c) for c in cmd)
        if cmd:
            snapshot(cmd, data.get("cwd") or os.getcwd(), str(data.get("session_id") or "s"), str(data.get("turn_id") or ""))
    except Exception as err:  # never stand between the model and its command
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(os.path.join(STATE, "errors.log"), "a") as f:
                f.write(f"{time.strftime('%F %T')} {type(err).__name__}: {err}\n")
        except OSError:
            pass
    return 0


def selftest():
    import tempfile
    global STATE
    bad = 0
    ro = ["cat a.py", "rg -n foo src | head", "git status && git diff", "ls -la; pwd", "sed -n 1,9p f", "curl -s https://x | jq .",
          "find . -name '*.py'", "python3 --version", "cat a 2>/dev/null", "grep x f 2>&1 | head", "ssh starlight uptime"]
    rw = ["edit_file a.py <<'E'\nx\nE", "sed -i s/a/b/ f", "echo x > f", "rm -rf build", "python3 a.py", "git commit -am x",
          "cat a > b", "sudo cat /etc/shadow", "find . -delete", "curl -o x https://y", "make", "npm install", "mv a b", "tee f"]
    for c in ro:
        if not read_only(c):
            print("SHOULD BE READ-ONLY:", c); bad += 1
    for c in rw:
        if read_only(c):
            print("SHOULD SNAPSHOT:", c); bad += 1
    with tempfile.TemporaryDirectory() as t:
        STATE = os.path.join(t, "state")
        proj = os.path.join(t, "proj")
        os.makedirs(os.path.join(proj, "src"))
        os.makedirs(os.path.join(proj, "node_modules", "x"))
        outside = os.path.join(t, "outside.conf")
        files = {"src/a.py": "a = 1\n", "src/b.py": "b = 2\n", "README": "hi\n", ".gitignore": ".env\n", ".env": "K=1\n",
                 "node_modules/x/i.js": "1\n"}
        for n, s in files.items():
            with open(os.path.join(proj, n), "w") as f:
                f.write(s)
        os.chmod(os.path.join(proj, "README"), 0o755)
        with open(outside, "w") as f:
            f.write("port 80\n")
        before = {n: open(os.path.join(proj, n)).read() for n in files}
        # One turn: a read, then writes by several routes, in the project and outside it.
        snapshot("cat src/a.py", proj, "S", "T1")
        if load(_key("S-T1")):
            print("a read made a snapshot"); bad += 1
        snapshot(f"sed -i s/1/9/ src/a.py && rm src/b.py && echo new > src/c.py; sed -i s/80/8080/ {outside}; echo K=2 > .env", proj, "S", "T1")
        snapshot("python3 -c 'open(\"src/d.py\",\"w\").write(\"d\")'", proj, "S", "T1")  # same turn: no second snapshot
        with open(os.path.join(proj, "src/a.py"), "w") as f:
            f.write("a = 9\n")
        os.remove(os.path.join(proj, "src/b.py"))
        for n, s in (("src/c.py", "new\n"), ("src/d.py", "d"), (".env", "K=2\n")):
            with open(os.path.join(proj, n), "w") as f:
                f.write(s)
        os.chmod(os.path.join(proj, "README"), 0o644)
        with open(outside, "w") as f:
            f.write("port 8080\n")
        rec = load(_key("S-T1"))
        if not rec or len(rec["dirs"]) != 1 or len(rec["commands"]) != 2:
            print("turn record wrong:", rec and (len(rec["dirs"]), len(rec["commands"]))); bad += 1
        todo = changes(rec)
        acts = sorted((a, os.path.relpath(p, proj)) for a, p, _ in todo)
        want = sorted([("restore", "src/a.py"), ("restore", "src/b.py"), ("remove", "src/c.py"), ("remove", "src/d.py"),
                       ("restore", "README"), ("restore", ".env"), ("restore", os.path.relpath(outside, proj))])
        if acts != want:
            print("changes wrong:", acts); bad += 1
        errs = undo(rec, todo)
        after = {n: open(os.path.join(proj, n)).read() for n in files if os.path.exists(os.path.join(proj, n))}
        if errs or after != before or os.path.exists(os.path.join(proj, "src/c.py")) or open(outside).read() != "port 80\n":
            print("undo didn't restore:", errs, {k for k in before if before.get(k) != after.get(k)}); bad += 1
        if not os.stat(os.path.join(proj, "README")).st_mode & 0o100:  # git keeps the exec bit, not the umask
            print("undo lost the mode"); bad += 1
        # Undoing the undo redoes.
        redo = records()[0]
        if not redo["key"].startswith("undo-"):
            print("no redo record"); bad += 1
        else:
            undo(redo, changes(redo))
            if open(os.path.join(proj, "src/a.py")).read() != "a = 9\n" or not os.path.exists(os.path.join(proj, "src/c.py")) \
                    or open(outside).read() != "port 8080\n":
                print("redo didn't redo"); bad += 1
        # Home and / are never snapshotted whole.
        if eligible(os.path.realpath(os.path.expanduser("~")))[0] or eligible("/")[0]:
            print("home or / eligible"); bad += 1
    total = len(ro) + len(rw) + 8
    print(f"undo_snapshot selftest: {total - bad}/{total} ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
