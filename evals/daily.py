#!/usr/bin/env python3
"""The daily tools that were only smoke-tested by hand: clip, sakura-decide (?decide/?why), sakura-morning, pa mail rules,
fmt, sakura-watch, sakura-pr, sakura-review, sakura-try, hear, say, and the part of sakura-red that isn't the model.
Graded by planted state, never by what a tool prints about itself: a clipboard that is a file, a decisions log read back
as JSON, a fixed day, planted envelopes behind a stand-in himalaya, the bytes of a file before and after a formatter,
a command that counts its own runs, a temp repo with real commits, and stand-ins on PATH (gh, sakura-launch, uv, piper,
aplay, curl) that record exactly what they were given.

  evals/daily.py              every case
  evals/daily.py --only NAME  one of: clip decide morning mail fmt watch pr review try hear say red
No model, no network, no display, no microphone, no speaker. Each case runs with a PATH that holds only its stand-ins,
bin/ and the handful of system tools named in BASE, so a real himalaya, gh or xclip on this machine is never reached.
A formatter that isn't installed here is a SKIP, not a pass.

Where the model does the work (the PR's wording, the review's findings, the notes from a recording) this proves what it
is handed and what the tool itself does and doesn't do around it, not the model's answer.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
SKIP = object()
# What bin/'s scripts may call from the system. Anything else on this machine is out of reach for a case.
BASE = (
    "bash sh env git cat mkdir rm sed grep head tail date hostname timeout dirname basename mktemp sleep ls touch tr "
    "sort cp mv chmod cut wc uname id tee true false diff awk find xargs readlink realpath stat df"
).split()
NOW = "2026-11-07T08:00:00"  # a Saturday

FAKE = """#!{python}
import json, os, sys
argv = sys.argv[1:]
def record(**extra):
    with open({log!r}, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(prog={name!r}, argv=argv, cwd=os.getcwd(), **extra)) + "\\n")
{body}
"""
# The model, standing in: it records the brief it was handed and says what it's told to.
LAUNCH = 'record()\nsys.stdout.write(os.environ.get("FAKE_LAUNCH_SAYS", ""))\nsys.exit(int(os.environ.get("FAKE_LAUNCH_RC", "0")))'
# gh, standing in: read-only answers from the environment; anything else it's asked is recorded and does nothing.
GH = """record()
a = argv
if a[:2] == ["repo", "view"]:
    d = os.environ.get("FAKE_GH_DEFAULT", "")
    if not d:
        sys.stderr.write("no git remotes found\\n")
        sys.exit(1)
    print(d)
elif a[:2] == ["pr", "list"] and "--head" in a:
    sys.stdout.write(os.environ.get("FAKE_GH_EXISTING", ""))
elif a[:2] == ["pr", "list"]:
    sys.stdout.write(os.environ.get("FAKE_GH_RECENT", ""))
elif a[:2] == ["pr", "view"]:
    sys.stdout.write(os.environ.get("FAKE_GH_META", ""))
elif a[:2] == ["pr", "diff"]:
    sys.stdout.write(os.environ.get("FAKE_GH_DIFF", ""))
"""


class Box:
    """A sealed place to run a tool: its own home, its own PATH, and a log of every stand-in that was called."""

    def __init__(self, tmp, name="box", tools=()):
        self.root = os.path.join(tmp, name)
        self.fakes, self.base, self.home = (
            os.path.join(self.root, d) for d in ("fakes", "base", "home")
        )
        self.log = os.path.join(self.root, "calls.jsonl")
        for d in (self.fakes, self.base, self.home):
            os.makedirs(d)
        os.symlink(os.path.realpath(sys.executable), os.path.join(self.base, "python3"))
        for t in list(BASE) + list(tools):
            p = shutil.which(t)
            if p:
                os.symlink(p, os.path.join(self.base, t))
        self.env = {
            "PATH": f"{self.fakes}:{BIN}:{self.base}",
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "SAKURA_HOME": os.path.join(self.home, ".sakura"),
            "XDG_CACHE_HOME": os.path.join(self.home, ".cache"),
            "XDG_DATA_HOME": os.path.join(self.home, ".local", "share"),
            "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
            "SAKURA_PA_DIR": os.path.join(self.home, ".sakura", "pa"),
            "SAKURA_TONIGHT_DIR": os.path.join(self.home, ".sakura", "tonight"),
            "SAKURA_GUARDIAN_DIR": os.path.join(self.home, ".sakura", "guardian"),
            "SAKURA_PA_NO_TIMER": "1",
            "SAKURA_TONIGHT_NO_TIMER": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Ana",
            "GIT_AUTHOR_EMAIL": "ana@example.com",
            "GIT_COMMITTER_NAME": "Ana",
            "GIT_COMMITTER_EMAIL": "ana@example.com",
        }

    def has(self, tool):
        return os.path.exists(os.path.join(self.base, tool))

    def fake(self, name, body="record()", where=None):
        path = os.path.join(where or self.fakes, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                FAKE.format(
                    python=os.path.realpath(sys.executable),
                    log=self.log,
                    name=name,
                    body=body,
                )
            )
        os.chmod(path, 0o755)
        return path

    def unfake(self, name):
        os.unlink(os.path.join(self.fakes, name))

    def run(self, args, cwd=None, stdin=None, env=None, timeout=120):
        e = dict(self.env)
        e.update(env or {})
        kw = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
        return subprocess.run(
            args,
            env=e,
            cwd=cwd or self.root,
            capture_output=True,
            text=True,
            timeout=timeout,
            **kw,
        )

    def tool(self, name, *args, **kw):
        return self.run([os.path.join(BIN, name)] + list(args), **kw)

    def calls(self, prog=None):
        try:
            rows = [json.loads(l) for l in open(self.log, encoding="utf-8")]
        except OSError:
            return []
        return [r for r in rows if prog is None or r["prog"] == prog]

    def clear(self):
        if os.path.exists(self.log):
            os.unlink(self.log)

    def git(self, cwd, *args):
        r = self.run(["git"] + list(args), cwd=cwd)
        if r.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout.strip()


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding=None if "b" in mode else "utf-8") as f:
        f.write(text)
    return path


def read(path, binary=False):
    try:
        with open(
            path, "rb" if binary else "r", encoding=None if binary else "utf-8"
        ) as f:
            return f.read()
    except OSError:
        return None


def gone(path):
    if os.path.exists(path):
        os.unlink(path)


def tree(root):
    """Every file under root with its bytes: what 'nothing was left behind' is checked against."""
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = read(p, binary=True)
    return out


# ── clip ─────────────────────────────────────────────────────────────────────

XCLIP = """store = os.environ["FAKE_CLIP_STORE"]
img = "image/png" in argv
if "-i" in argv:
    data = sys.stdin.buffer.read()
    record(stdin_bytes=len(data))
    if os.environ.get("FAKE_CLIP_REFUSES"):
        sys.stderr.write("Error: Can't open display\\n")
        sys.exit(1)
    open(store, "wb").write(data)
else:
    record()
    path = store + ".png" if img else store
    if not os.path.exists(path) or not os.path.getsize(path):
        sys.stderr.write("Error: target STRING not available\\n")
        sys.exit(1)
    sys.stdout.buffer.write(open(path, "rb").read())
"""
WLCOPY = """data = sys.stdin.buffer.read()
record(stdin_bytes=len(data))
open(os.environ["FAKE_CLIP_STORE"], "wb").write(data)
"""
WLPASTE = """record()
path = os.environ["FAKE_CLIP_STORE"] + (".png" if "image/png" in argv else "")
if not os.path.exists(path) or not os.path.getsize(path):
    sys.stderr.write("Nothing is copied\\n")
    sys.exit(1)
sys.stdout.buffer.write(open(path, "rb").read())
"""


def clip(tmp):
    b = Box(tmp)
    store = os.path.join(b.root, "clipboard")
    for name, body in (("xclip", XCLIP), ("wl-copy", WLCOPY), ("wl-paste", WLPASTE)):
        b.fake(name, body)
    x11 = {"DISPLAY": ":9", "FAKE_CLIP_STORE": store}
    wl = {"WAYLAND_DISPLAY": "wayland-9", "FAKE_CLIP_STORE": store}
    text = "first line\n  second\tline, with नमस्ते and a 'quote' $HOME\n"

    put = b.tool("clip", "set", stdin=text, env=x11)
    stored = read(store)
    got = b.tool("clip", env=x11)
    piped = b.run(
        ["bash", "-c", f"printf 'from a command\\n' | {BIN}/clip set && {BIN}/clip"],
        env=x11,
    )

    gone(store)
    b.clear()
    wput = b.tool("clip", "set", stdin=text, env=wl)
    wstored = read(store)
    wgot = b.tool("clip", env=wl)
    wprogs = [c["prog"] for c in b.calls()]

    gone(store)
    empty = b.tool("clip", env=x11)

    b.clear()
    blind = b.tool("clip", env={"FAKE_CLIP_STORE": store})
    blind_set = b.tool("clip", "set", stdin="x", env={"FAKE_CLIP_STORE": store})
    blind_calls = b.calls()

    # A command that takes longer than the clipboard's 3 s limit: all of it has to arrive.
    slow = b.run(["bash", "-c", f"(sleep 4; echo late) | {BIN}/clip set"], env=x11)
    slow_stored = read(store)

    gone(store)
    refused = b.tool("clip", "set", stdin="lost", env=dict(x11, FAKE_CLIP_REFUSES="1"))

    png = b"\x89PNG\r\n\x1a\n" + os.urandom(64)
    write(store + ".png", png, "wb")
    out = os.path.join(b.root, "shot.png")
    img = b.tool("clip", "image", out, env=wl)
    img_x = b.tool("clip", "image", out + ".x", env=x11)
    os.unlink(store + ".png")
    noimg = b.tool("clip", "image", os.path.join(b.root, "none.png"), env=wl)
    bad = b.tool("clip", "frobnicate", env=x11)
    return {
        "what goes in with `clip set` is on the clipboard, byte for byte": put.returncode
        == 0
        and stored == text,
        "`clip` prints it back unchanged": got.returncode == 0 and got.stdout == text,
        "`cmd | clip set` takes a command's output": piped.returncode == 0
        and piped.stdout == "from a command\n",
        "on Wayland alone it goes through wl-copy and wl-paste, not xclip": wput.returncode
        == 0
        and wstored == text
        and wgot.stdout == text
        and "xclip" not in wprogs
        and {"wl-copy", "wl-paste"} <= set(wprogs),
        "an empty clipboard is exit 1 with nothing on stdout": empty.returncode == 1
        and empty.stdout == ""
        and "nothing on the clipboard" in empty.stderr,
        "with no display it says so and touches no clipboard tool": blind.returncode
        == 1
        and blind_set.returncode == 1
        and "no display" in blind.stderr
        and blind_calls == [],
        "a command slower than the clipboard's 3 s limit still lands whole": slow.returncode
        == 0
        and slow_stored == "late\n",
        "a clipboard that refuses is exit 1 and said, not silence": refused.returncode
        == 1
        and "clip:" in refused.stderr
        and read(store) is None,
        "`clip image F` saves the clipboard's image, on Wayland and on X11": img.returncode
        == 0
        and read(out, True) == png
        and read(out + ".x", True) == png
        and img_x.returncode == 0,
        "no image on the clipboard leaves no file behind": noimg.returncode == 1
        and not os.path.exists(os.path.join(b.root, "none.png")),
        "an unknown subcommand is exit 2": bad.returncode == 2,
    }


# ── sakura-decide ────────────────────────────────────────────────────────────


def decide(tmp):
    b = Box(tmp)
    log = os.path.join(b.env["SAKURA_HOME"], "decisions.jsonl")
    shop, blog, plain = (os.path.join(b.root, d) for d in ("shop", "blog", "plain"))
    for repo, branch in ((shop, "feature/queue"), (blog, "main")):
        os.makedirs(repo)
        b.git(repo, "init", "-q", "-b", branch)
        write(os.path.join(repo, "a.txt"), "a\n")
        b.git(repo, "add", "-A")
        b.git(repo, "commit", "-qm", "initial")
    os.makedirs(plain)
    sub = os.path.join(shop, "src", "deep")
    os.makedirs(sub)

    nothing = b.tool("sakura-decide", cwd=shop)
    no_file_yet = not os.path.exists(log)
    none_yet = b.tool("sakura-decide", "why", cwd=shop)

    first = "Redis for the queue: Postgres LISTEN/NOTIFY dropped jobs under load in the Oct test"
    odd = "Quote \"it\" & 'them'; cost $(touch pwned) `touch pwned2` 100% → नेपाली ok\nsecond line: because \\n isn't a newline"
    b.tool("sakura-decide", first, cwd=sub)
    b.tool(
        "sakura-decide",
        "Static pages, no CMS: one author, and the build is the backup",
        cwd=blog,
    )
    b.tool(
        "sakura-decide",
        "Paper notebook for the queue of chores: screens after nine keep me up",
        cwd=plain,
    )
    b.tool("sakura-decide", odd, cwd=shop)
    rows = [json.loads(l) for l in (read(log) or "").splitlines()]
    head = b.git(shop, "rev-parse", "--short", "HEAD")

    why_queue = b.tool("sakura-decide", "why", "queue", cwd=plain)
    why_two = b.tool("sakura-decide", "why", "QUEUE", "postgres", cwd=blog)
    why_repo = b.tool("sakura-decide", "why", "blog", cwd=plain)
    why_none = b.tool("sakura-decide", "why", "kubernetes", cwd=shop)
    last_one = b.tool("sakura-decide", "list", "1", cwd=plain)
    exp_shop = b.tool("sakura-decide", "export", cwd=shop)
    exp_blog = b.tool("sakura-decide", "export", cwd=blog)
    exp_all = b.tool("sakura-decide", "export", cwd=plain)

    # A line cut short by a crash, in the middle of the log: the others must still answer.
    lines = (read(log) or "").splitlines()
    write(
        log,
        "\n".join(
            lines[:2] + ['{"when": "2026-11-0', "not json at all", "[1, 2]"] + lines[2:]
        )
        + "\n",
    )
    after_damage = b.tool("sakura-decide", "why", "queue", cwd=plain)
    b.tool("sakura-decide", "Still writing after the damage: yes", cwd=plain)
    recall = b.tool(
        "sakura-recall",
        "LISTEN/NOTIFY",
        cwd=plain,
        env={"SAKURA_SESSIONS_DIR": os.path.join(b.root, "no-sessions")},
    )
    return {
        "nothing to record is refused and writes no log": nothing.returncode != 0
        and no_file_yet,
        "?why on an empty log says how to start, exit 1": none_yet.returncode == 1
        and "?decide" in none_yet.stdout,
        "a decision is one JSON line with its exact text": len(rows) == 4
        and rows[0]["text"] == first,
        "it carries the repo, branch and commit it was made in, from a subdirectory too": rows[
            0
        ]["repo"]
        == "shop"
        and rows[0]["branch"] == "feature/queue"
        and rows[0]["commit"] == head
        and os.path.realpath(rows[0]["dir"]) == os.path.realpath(sub),
        "outside a repo it carries the directory instead": rows[2]["repo"] == ""
        and rows[2]["commit"] == ""
        and os.path.realpath(rows[2]["dir"]) == os.path.realpath(plain),
        "quotes, $(...), backticks, a newline and नेपाली survive exactly, and nothing in them runs": rows[
            3
        ]["text"]
        == odd
        and not os.path.exists(os.path.join(shop, "pwned"))
        and not os.path.exists(os.path.join(shop, "pwned2")),
        "?why WORD finds it from anywhere, newest first": why_queue.returncode == 0
        and 0
        <= why_queue.stdout.find("Paper notebook")
        < why_queue.stdout.find("Redis for the queue")
        and "Static pages" not in why_queue.stdout,
        "?why shows where it was decided": "shop feature/queue@" + head
        in why_queue.stdout
        and plain in why_queue.stdout,
        "every word has to match, in any case": "Redis for the queue" in why_two.stdout
        and "Paper notebook" not in why_two.stdout,
        "a repo's name finds its decisions": "Static pages" in why_repo.stdout
        and "Redis" not in why_repo.stdout,
        "no match is exit 1 and says so": why_none.returncode == 1
        and "no decision recorded about that" in why_none.stdout,
        "list 1 is only the newest": "Quote" in last_one.stdout
        and "Redis" not in last_one.stdout
        and "Static" not in last_one.stdout,
        "export in a repo is that repo's decisions only": "Redis for the queue"
        in exp_shop.stdout
        and "Quote" in exp_shop.stdout
        and "Static pages" not in exp_shop.stdout
        and "Paper notebook" not in exp_shop.stdout
        and "Static pages" in exp_blog.stdout
        and "Redis" not in exp_blog.stdout,
        "export outside a repo is all of them": all(
            w in exp_all.stdout
            for w in ("Redis for the queue", "Static pages", "Paper notebook")
        ),
        "a damaged line in the log doesn't hide the rest": after_damage.returncode == 0
        and "Redis for the queue" in after_damage.stdout
        and "Paper notebook" in after_damage.stdout
        and "Traceback" not in after_damage.stderr,
        "sakura-recall finds a decision by its words, damaged log or not": recall.returncode
        == 0
        and "LISTEN/NOTIFY dropped jobs" in recall.stdout,
    }


# ── sakura-morning ───────────────────────────────────────────────────────────


def morning(tmp):
    b = Box(tmp)
    finding = os.path.join(b.root, "guardian.txt")
    install = os.path.join(b.root, "doctor.txt")
    # The guardian and the doctor read this machine (disks, units, the install); here they say what's planted for them.
    b.fake(
        "sakura-guardian",
        f'record()\ntry:\n    sys.stdout.write(open({finding!r}).read())\nexcept OSError:\n    print("nothing to worry about")',
    )
    b.fake(
        "sakura-doctor",
        f"record()\ntry:\n    sys.stdout.write(open({install!r}).read())\nexcept OSError:\n    pass",
    )
    write(
        os.path.join(b.env["SAKURA_PA_DIR"], "settings.json"),
        json.dumps({"roles": ["everyone"]}),
    )
    env = {"SAKURA_PA_NOW": NOW}
    stamp = os.path.join(b.env["SAKURA_HOME"], "morning-shown")
    reports = os.path.join(b.env["SAKURA_TONIGHT_DIR"], "reports")

    quiet = b.tool("sakura-morning", env=env)
    no_stamp = not os.path.exists(stamp)

    def report(day, weekday, line):
        write(
            os.path.join(reports, f"{day}.md"),
            f"# Night shift, {weekday} {day}, started 01:00\n\n{line}\n\nEach job ran as a worker.\n",
        )

    report("2026-11-03", "Tuesday", "1 of 1 passed. Finished 01:09.")
    stale = b.tool("sakura-morning", env=env)

    write(finding, "disk /srv is 96% full (4.1 GB left)\n")
    write(
        install,
        "ok    82 commands answer --help\nFAIL  hooks/recall_context.py is not linked\nWARN  ~/.local/bin is not on PATH\n",
    )
    report("2026-11-06", "Friday", "2 of 3 passed. Finished 01:40.")
    write(
        os.path.join(b.env["SAKURA_TONIGHT_DIR"], "queue.json"),
        json.dumps(
            {
                "at": "01:00",
                "seq": 1,
                "jobs": [
                    {
                        "id": 1,
                        "status": "queued",
                        "dir": "/srv/shop",
                        "brief": "run the slow tests",
                        "settings": {},
                    }
                ],
            }
        ),
    )
    b.tool("pa", "todo", "add", "file the tax return due:2026-11-07", env=env)
    b.tool("pa", "remind", "10am", "call", "the", "bank", env=env)
    full = b.tool("sakura-morning", env=env)

    report("2026-11-07", "Saturday", "5 of 5 passed. Finished 02:10.")
    same_day = b.tool("sakura-morning", env=env)

    once1 = b.tool("sakura-morning", "--once", env=env)
    stamped = (read(stamp) or "").strip()
    once2 = b.tool("sakura-morning", "--once", env=env)
    by_name = b.tool("sakura-morning", env=env)
    later = b.tool(
        "sakura-morning", "--once", env={"SAKURA_PA_NOW": "2026-11-07T23:59:00"}
    )
    next_day = b.tool(
        "sakura-morning", "--once", env={"SAKURA_PA_NOW": "2026-11-08T00:01:00"}
    )
    q = quiet.stdout
    return {
        "the page is headed with the day it is": q.startswith("Saturday 7 November, ")
        and quiet.returncode == 0,
        "a quiet day is short: a calm guardian and nothing that needs you": "guardian: nothing to worry about"
        in q
        and "Nothing needs you." in q,
        "sections with nothing to show aren't there": not any(
            w in q
            for w in ("night shift", "queued", "install:", "To-do", "Reminders", "Mail")
        ),
        "a report from four nights ago isn't last night's": "night shift:"
        not in stale.stdout
        and "1 of 1 passed" not in stale.stdout,
        "what the guardian found is on the page": "disk /srv is 96% full" in full.stdout
        and "nothing to worry about" not in full.stdout,
        "a broken install shows its FAIL and WARN lines, not the ok ones": "install:"
        in full.stdout
        and "FAIL  hooks/recall_context.py" in full.stdout
        and "WARN  ~/.local/bin" in full.stdout
        and "82 commands" not in full.stdout,
        "last night's report is one line": "night shift: 2 of 3 passed. Finished 01:40."
        in full.stdout,
        "tonight's queue is counted": "night shift at 01:00; 1 queued" in full.stdout,
        "what's due today and the day's reminders come from pa": "To-do" in full.stdout
        and "file the tax return" in full.stdout
        and "Reminders" in full.stdout
        and "call the bank" in full.stdout
        and "Nothing needs you." not in full.stdout,
        "a report finished this morning is shown too": "night shift: 5 of 5 passed. Finished 02:10."
        in same_day.stdout,
        "by name it prints every time and leaves the once-a-day mark alone": no_stamp
        and by_name.stdout.startswith("Saturday 7 November"),
        "--once prints the first time and records the day": once1.stdout.startswith(
            "Saturday 7 November"
        )
        and stamped == "2026-11-07",
        "--once is silent for the rest of that day": once2.stdout == ""
        and once2.returncode == 0
        and later.stdout == ""
        and later.returncode == 0,
        "--once speaks again the next morning": next_day.stdout.startswith(
            "Sunday 8 November"
        )
        and (read(stamp) or "").strip() == "2026-11-08",
    }


# ── pa mail rules ────────────────────────────────────────────────────────────


def mail(tmp):
    b = Box(tmp)
    planted = os.path.join(b.root, "envelopes.json")
    b.fake(
        "himalaya",
        f'record()\nif argv[:2] == ["envelope", "list"]:\n    sys.stdout.write(open({planted!r}).read())\nelse:\n    sys.exit(1)',
    )
    # himalaya 1.x calls the address "addr"; older output and pa's own tests call it "email". Both are planted.
    write(
        planted,
        json.dumps(
            [
                {
                    "id": "5",
                    "flags": [],
                    "subject": "50% off everything",
                    "from": {"name": "Shop Deals", "addr": "newsletter@shop.example"},
                    "date": "2026-11-07 07:10+00:00",
                },
                {
                    "id": "4",
                    "flags": [],
                    "subject": "lunch on Tuesday?",
                    "from": {"name": "Priya Sharma", "addr": "ps@corp.example"},
                    "date": "2026-11-07 07:00+00:00",
                },
                {
                    "id": "3",
                    "flags": [],
                    "subject": "Q4 numbers",
                    "from": {"name": None, "email": "boss@corp.example"},
                    "date": "2026-11-07 06:00+00:00",
                },
                {
                    "id": "2",
                    "flags": ["Seen"],
                    "subject": "already read",
                    "from": {"name": "Boss", "addr": "boss@corp.example"},
                    "date": "2026-11-06 06:00+00:00",
                },
                {
                    "id": "1",
                    "flags": [],
                    "subject": "Build 812: server down",
                    "from": {"name": "CI", "addr": "ci@build.example"},
                    "date": "2026-11-06 05:00+00:00",
                },
            ]
        ),
    )
    settings = os.path.join(b.env["SAKURA_PA_DIR"], "settings.json")
    write(settings, json.dumps({"roles": ["everyone"]}))
    env = {"SAKURA_PA_NOW": NOW}

    def rules():
        return json.loads(read(settings) or "{}").get("mail_rules")

    def section():
        """The brief's Mail section as its lines, or None when the section isn't there."""
        out = b.tool("pa", "brief", env=env).stdout.splitlines()
        if "Mail" not in out:
            return None
        got = []
        for line in out[out.index("Mail") + 1 :]:
            if not line.startswith("  "):
                break
            got.append(line.strip())
        return got

    before = section()
    b.tool("pa", "mail", "urgent", "boss@", env=env)
    b.tool("pa", "mail", "mute", "newsletter", env=env)
    b.tool("pa", "mail", "urgent", "boss@", env=env)
    stored = rules()
    listed = b.tool("pa", "mail", "rules", env=env)
    after = section()
    asked = [c["argv"] for c in b.calls("himalaya")]

    b.tool("pa", "mail", "urgent", "priya", env=env)
    by_name = section()
    b.tool("pa", "mail", "urgent", "Server", "Down", env=env)
    by_subject = section()

    b.tool("pa", "mail", "forget", "newsletter", env=env)
    forgotten = rules()
    back = section()
    bad = b.tool("pa", "mail", "frobnicate", "x", env=env)
    unchanged = rules() == forgotten
    for word in ("@",):
        b.tool("pa", "mail", "mute", word, env=env)
    all_muted = section()
    return {
        "with no rules, unread mail is listed as it came and read mail isn't": before
        == [
            "4 unread",
            "newsletter@shop.example: 50% off everything",
            "ps@corp.example: lunch on Tuesday?",
            "boss@corp.example: Q4 numbers",
            "ci@build.example: Build 812: server down",
        ],
        "the rules are on disk, each once": stored
        == {"urgent": ["boss@"], "mute": ["newsletter"]},
        "pa mail rules lists them": "urgent: boss@" in listed.stdout
        and "mute: newsletter" in listed.stdout,
        "an urgent sender comes first, marked": after is not None
        and after[:2] == ["3 unread, 1 urgent", "! boss@corp.example: Q4 numbers"],
        "a muted sender is hidden and not counted": after is not None
        and not any("50% off" in l or "newsletter" in l for l in after)
        and after[2:]
        == [
            "ps@corp.example: lunch on Tuesday?",
            "ci@build.example: Build 812: server down",
        ],
        "the brief only reads the inbox": asked != []
        and all(a[:2] == ["envelope", "list"] for a in asked),
        "a rule matches the sender's name, not only the address": by_name is not None
        and by_name[0] == "3 unread, 2 urgent"
        and "! ps@corp.example: lunch on Tuesday?" in by_name,
        "a rule matches the subject, in any case": by_subject is not None
        and by_subject[0] == "3 unread, 3 urgent"
        and "! ci@build.example: Build 812: server down" in by_subject,
        "forget removes the rule from disk and the mail comes back": forgotten
        is not None
        and forgotten["mute"] == []
        and back is not None
        and "newsletter@shop.example: 50% off everything" in back
        and back[0].startswith("4 unread"),
        "an unknown rule kind is refused and changes nothing": bad.returncode != 0
        and unchanged,
        "with everything muted there's no Mail section at all": all_muted is None,
    }


# ── fmt ──────────────────────────────────────────────────────────────────────

# language: (file, badly formatted, what the formatter makes of it, the tools it needs)
FMT = {
    "python (ruff)": (
        "bad.py",
        "def f( a ):\n    return  a\n",
        "def f(a):\n    return a\n",
        ("ruff",),
    ),
    "json (prettier)": (
        "bad.json",
        '{"a":1,"b":[1,2]}',
        '{ "a": 1, "b": [1, 2] }\n',
        ("prettier", "node"),
    ),
    "shell (shfmt)": (
        "bad.sh",
        "#!/bin/sh\nif true;then\necho hi\nfi\n",
        "#!/bin/sh\nif true; then\n    echo hi\nfi\n",
        ("shfmt",),
    ),
    "go (gofmt)": (
        "bad.go",
        "package main\n\nfunc main() {\nprintln(1)\n}\n",
        "package main\n\nfunc main() {\n\tprintln(1)\n}\n",
        ("gofmt",),
    ),
}


def fmt(tmp):
    b = Box(tmp, tools=("ruff", "prettier", "node", "shfmt", "shellcheck", "gofmt"))
    out = {}
    loose = os.path.join(b.root, "loose")
    os.makedirs(loose)
    for lang, (name, bad, good, needs) in FMT.items():
        if not all(b.has(t) for t in needs):
            for claim in (
                "--check exits 1 and changes nothing",
                "a plain run formats it",
                "--check on the result is exit 0",
            ):
                out[f"{lang}: {claim} ({needs[0]} isn't installed here)"] = SKIP
            continue
        path = write(os.path.join(loose, name), bad)
        check = b.tool("fmt", "--check", name, cwd=loose)
        out[f"{lang}: --check exits 1 and changes nothing"] = (
            check.returncode == 1
            and read(path) == bad
            and "would change" in check.stdout
        )
        fix = b.tool("fmt", name, cwd=loose)
        out[f"{lang}: a plain run formats it"] = (
            fix.returncode == 0 and read(path) == good
        )
        clean = b.tool("fmt", "--check", name, cwd=loose)
        out[f"{lang}: --check on the result is exit 0"] = (
            clean.returncode == 0
            and read(path) == good
            and "would change" not in clean.stdout
        )

    if not b.has("ruff"):
        for claim in (
            "only the changed files are formatted",
            "--staged is the staged files only",
            "from a subdirectory it finds the changed files there",
            "a clean tree is nothing to do",
            "--help prints the manual and a mistyped option is exit 2: neither formats anything",
            "a file the formatter can't parse is exit 1 and untouched",
        ):
            out[f"{claim} (ruff isn't installed here)"] = SKIP
    else:
        bad = FMT["python (ruff)"][1]
        edit, fixed = "y  =  2\n", "y = 2\n"
        repo = os.path.join(b.root, "repo")
        os.makedirs(os.path.join(repo, "pkg"))
        b.git(repo, "init", "-q", "-b", "main")
        for name in ("old.py", "mod.py", "st.py", "pkg/deep.py"):
            write(os.path.join(repo, name), bad)
        b.git(repo, "add", "-A")
        b.git(repo, "commit", "-qm", "as it was")
        nothing = b.tool("fmt", cwd=repo)
        untouched = all(
            read(os.path.join(repo, n)) == bad
            for n in ("old.py", "mod.py", "st.py", "pkg/deep.py")
        )
        write(os.path.join(repo, "mod.py"), edit)
        helped = b.tool("fmt", "--help", cwd=repo)
        typo = b.tool("fmt", "--chekc", cwd=repo)
        out[
            "--help prints the manual and a mistyped option is exit 2: neither formats anything"
        ] = (
            helped.returncode == 0
            and "fmt --check" in helped.stdout
            and typo.returncode == 2
            and "--chekc" in typo.stderr
            and read(os.path.join(repo, "mod.py")) == edit
        )
        for name in ("mod.py", "st.py", "pkg/deep.py", "new.py"):
            write(os.path.join(repo, name), edit)
        b.git(repo, "add", "st.py")
        b.tool("fmt", "--staged", cwd=repo)
        state = {
            n: read(os.path.join(repo, n))
            for n in ("old.py", "mod.py", "st.py", "pkg/deep.py", "new.py")
        }
        out["--staged is the staged files only"] = state["st.py"] == fixed and all(
            state[n] == edit for n in ("mod.py", "pkg/deep.py", "new.py")
        )
        sub = b.tool("fmt", cwd=os.path.join(repo, "pkg"))
        out["from a subdirectory it finds the changed files there"] = (
            sub.returncode == 0
            and read(os.path.join(repo, "pkg", "deep.py")) == fixed
            and read(os.path.join(repo, "mod.py")) == edit
        )
        b.tool("fmt", cwd=repo)
        state = {n: read(os.path.join(repo, n)) for n in ("old.py", "mod.py", "new.py")}
        out[
            "only the changed files are formatted: modified and new ones, not a committed one"
        ] = (
            state["mod.py"] == fixed
            and state["new.py"] == fixed
            and state["old.py"] == bad
        )
        out["a clean tree is nothing to do"] = (
            nothing.returncode == 0
            and "nothing to format" in nothing.stdout
            and untouched
        )
        broken = write(os.path.join(loose, "broken.py"), "def f(:\n  return\n")
        r = b.tool("fmt", "broken.py", cwd=loose)
        out["a file the formatter can't parse is exit 1 and untouched"] = (
            r.returncode == 1
            and read(broken) == "def f(:\n  return\n"
            and "Traceback" not in r.stderr
        )

    # A machine with no formatters at all, and one with only the shell linter.
    bare = Box(tmp, "bare")
    for name, text in (
        ("a.py", "x  =  1\n"),
        ("a.lua", "local  x=1\n"),
        ("a.rs", "fn  main(){}\n"),
    ):
        write(os.path.join(bare.root, name), text)
    none = bare.tool("fmt", "a.py", "a.lua", "a.rs")
    none_check = bare.tool("fmt", "--check", "a.py", "a.lua", "a.rs")
    out["a missing formatter is named, skipped and exit 0, with the file untouched"] = (
        none.returncode == 0
        and none_check.returncode == 0
        and all(w in none.stdout for w in ("ruff", "stylua", "rustfmt"))
        and "Traceback" not in none.stderr
        and read(os.path.join(bare.root, "a.py")) == "x  =  1\n"
        and "✓" not in none.stdout
    )
    odd = bare.tool("fmt", "notes.txt")
    out["a file with no formatter is said so, exit 0"] = (
        odd.returncode == 0 and "no" in odd.stdout and "Traceback" not in odd.stderr
    )
    lint = Box(tmp, "lintonly", tools=("shellcheck",))
    if not lint.has("shellcheck"):
        out[
            "a linter alone is never passed off as a formatter (shellcheck isn't installed here)"
        ] = SKIP
    else:
        sh = write(
            os.path.join(lint.root, "a.sh"), "#!/bin/sh\nif true;then\necho $1\nfi\n"
        )
        r = lint.tool("fmt", "a.sh")
        c = lint.tool("fmt", "--check", "a.sh")
        with_lint = lint.tool("fmt", "--lint", "a.sh")
        out["a linter alone is never passed off as a formatter"] = (
            r.returncode == 0
            and "✓" not in r.stdout
            and "shfmt" in r.stdout
            and c.returncode == 0
            and "would change" not in c.stdout
            and read(sh) == "#!/bin/sh\nif true;then\necho $1\nfi\n"
        )
        out["--lint prints the linter's findings and is exit 1"] = (
            with_lint.returncode == 1 and "SC2086" in with_lint.stdout
        )
    return out


# ── sakura-watch ─────────────────────────────────────────────────────────────


def watch(tmp):
    b = Box(tmp)
    b.fake("sakura-launch", LAUNCH)
    d = os.path.join(b.root, "w")
    os.makedirs(d)
    tick = write(
        os.path.join(d, "tick"),
        '#!/bin/sh\nf="$(dirname "$0")/n"\nn=$(($(cat "$f" 2>/dev/null || echo 0) + 1))\necho "$n" > "$f"\necho "static line"\necho "tick $n"\n',
    )
    args = write(os.path.join(d, "args"), '#!/bin/sh\necho "got: $*"\n')
    os.chmod(tick, 0o755)
    os.chmod(args, 0o755)
    counter = os.path.join(d, "n")

    started = time.time()
    r = b.tool("sakura-watch", "-n", "0.05", "--count", "3", tick, timeout=60)
    took = time.time() - started
    runs = (read(counter) or "").strip()
    lines = r.stdout.splitlines()
    heads = [l for l in lines if l.startswith("every 0.05s")]

    same = b.tool(
        "sakura-watch", "-n", "0.05", "--count", "3", "echo", "same", timeout=60
    )
    own = b.tool(
        "sakura-watch",
        "--count",
        "1",
        args,
        "-h",
        "-n",
        "5",
        "--count",
        "--explain",
        timeout=60,
    )

    unasked = b.calls("sakura-launch")
    os.unlink(counter)
    b.clear()
    ex = b.tool(
        "sakura-watch",
        "-n",
        "0.05",
        "--explain",
        "--count",
        "3",
        tick,
        env={"FAKE_LAUNCH_SAYS": "the counter went up by one\n"},
        timeout=60,
    )
    asked = b.calls("sakura-launch")
    bad_n = b.tool("sakura-watch", "-n", "soon", "echo", "x", timeout=60)
    bad_count = b.tool("sakura-watch", "--count", "0", "echo", "x", timeout=60)
    none = b.tool("sakura-watch", timeout=60)
    return {
        "--count 3 runs the command three times and stops": r.returncode == 0
        and runs == "3"
        and took < 30,
        "a changed line is shown as what it was and what it is": "- tick 1" in lines
        and "+ tick 2" in lines
        and "- tick 2" in lines
        and "+ tick 3" in lines,
        "a line that didn't change isn't marked": lines.count("static line") == 3
        and not any(l in ("- static line", "+ static line") for l in lines),
        "each run's header counts the changes so far, the one it shows included": len(
            heads
        )
        == 3
        and [h.rsplit("(", 1)[-1] for h in heads]
        == ["0 changes)", "1 change)", "2 changes)"],
        "output that stays the same shows no change": same.stdout.count("\nsame") == 3
        and "+ " not in same.stdout
        and "- " not in same.stdout
        and "(1 change" not in same.stdout,
        "the command's own options are its own (-h, -n after the command)": own.returncode
        == 0
        and "got: -h -n 5 --count --explain" in own.stdout,
        "without --explain the model is never called": unasked == []
        and "sakura:" not in r.stdout,
        "--explain asks once per change, with the diff, in a one-shot run": len(asked)
        == 2
        and all(a["argv"][:2] == ["--exec", "--skip-git-repo-check"] for a in asked)
        and "-tick 1" in asked[0]["argv"][-1]
        and "+tick 2" in asked[0]["argv"][-1]
        and "+tick 3" in asked[1]["argv"][-1],
        "the explanation is shown under the output": "sakura: the counter went up by one"
        in ex.stdout,
        "a bad -n or --count is exit 2 with a sentence, not a traceback": bad_n.returncode
        == 2
        and bad_count.returncode == 2
        and "Traceback" not in bad_n.stderr + bad_count.stderr
        and "sakura-watch:" in bad_n.stderr,
        "no command is exit 2": none.returncode == 2,
    }


# ── sakura-pr, sakura-review ─────────────────────────────────────────────────


def shop_repo(b):
    """origin (bare) and a clone-like work tree: main ← develop (one commit) ← feature/tax (two commits, not pushed)."""
    origin, work = os.path.join(b.root, "origin.git"), os.path.join(b.root, "shop")
    os.makedirs(work)
    b.git(b.root, "init", "-q", "--bare", "-b", "main", origin)
    b.git(work, "init", "-q", "-b", "main")
    write(os.path.join(work, "app.py"), "PRICE = 100\n")
    b.git(work, "add", "-A")
    b.git(work, "commit", "-qm", "initial price")
    b.git(work, "remote", "add", "origin", origin)
    b.git(work, "push", "-q", "-u", "origin", "main")
    b.git(work, "checkout", "-q", "-b", "develop")
    write(os.path.join(work, "app.py"), "DEV_ONLY = 1\n", "a")
    b.git(work, "commit", "-qam", "dev only change")
    b.git(work, "push", "-q", "-u", "origin", "develop")
    b.git(work, "checkout", "-q", "-b", "feature/tax")
    write(os.path.join(work, "app.py"), "TAX = 0.13\n", "a")
    b.git(work, "commit", "-qam", "add the tax rate")
    write(
        os.path.join(work, "app.py"),
        "def total(p):\n    return round(p * (1 + TAX), 2)\n",
        "a",
    )
    b.git(
        work,
        "commit",
        "-qam",
        "round totals",
        "-m",
        "Two decimals, as the invoices print them.",
    )
    return origin, work


def master_repo(b):
    """A repo whose default branch is master, with no GitHub behind it: feat is one commit ahead."""
    work = os.path.join(b.root, "legacy")
    os.makedirs(work)
    b.git(work, "init", "-q", "-b", "master")
    write(os.path.join(work, "lib.py"), "A = 1\n")
    b.git(work, "add", "-A")
    b.git(work, "commit", "-qm", "first on master")
    b.git(work, "checkout", "-q", "-b", "feat")
    write(os.path.join(work, "lib.py"), "B_ON_FEAT = 2\n", "a")
    b.git(work, "commit", "-qam", "add b on feat")
    return work


def verbs(b):
    return {" ".join(c["argv"][:2]) for c in b.calls("gh")}


def pr(tmp):
    b = Box(tmp)
    b.fake("gh", GH)
    b.fake("sakura-launch", LAUNCH)
    work = shop_repo(b)[1]
    gh = {"FAKE_GH_DEFAULT": "main"}
    shorts = b.git(work, "log", "--format=%h", "-3").split()

    p = b.tool("sakura-pr", "--print", cwd=work, env=gh)
    brief = p.stdout
    dev = b.tool("sakura-pr", "--print", "--base", "develop", cwd=work, env=gh).stdout
    gh_says = b.tool(
        "sakura-pr", "--print", cwd=work, env={"FAKE_GH_DEFAULT": "develop"}
    ).stdout
    no_gh = b.tool("sakura-pr", "--print", cwd=work).stdout
    draft = b.tool("sakura-pr", "--print", "--draft", cwd=work, env=gh).stdout
    worded = b.tool(
        "sakura-pr", "--print", "draft", "mention", "the", "rounding", cwd=work, env=gh
    ).stdout
    existing = b.tool(
        "sakura-pr",
        "--print",
        cwd=work,
        env=dict(gh, FAKE_GH_EXISTING="https://github.com/acme/shop/pull/41\n"),
    ).stdout
    styled = b.tool(
        "sakura-pr",
        "--print",
        cwd=work,
        env=dict(gh, FAKE_GH_RECENT="## Speed up checkout\nCaches the cart.\n"),
    ).stdout
    printed_only = b.calls("sakura-launch") == []

    b.clear()
    ex = b.tool("sakura-pr", "--exec", cwd=work, env=gh)
    tui = b.tool("sakura-pr", cwd=work, env=gh)
    launched = b.calls("sakura-launch")
    gh_verbs = verbs(b)

    write(
        os.path.join(work, ".github", "pull_request_template.md"),
        "## What changed\n## Checklist-7c1\n",
    )
    write(os.path.join(work, "scratch.txt"), "not committed\n")
    templated = b.tool("sakura-pr", "--print", cwd=work, env=gh).stdout
    shutil.rmtree(os.path.join(work, ".github"))
    os.unlink(os.path.join(work, "scratch.txt"))
    b.git(work, "push", "-q", "-u", "origin", "feature/tax")
    pushed = b.tool("sakura-pr", "--print", cwd=work, env=gh).stdout

    # git allows this as a branch name. It must stay a name.
    b.git(work, "checkout", "-q", "-b", "x$(touch${IFS}pwned)")
    hostile = b.tool("sakura-pr", "--print", cwd=work, env=gh)
    ran = os.path.exists(os.path.join(work, "pwned"))

    b.clear()
    b.git(work, "checkout", "-q", "main")
    on_base = b.tool("sakura-pr", "--exec", cwd=work, env=gh)
    b.git(work, "checkout", "-q", "--detach", "feature/tax")
    detached = b.tool("sakura-pr", "--exec", cwd=work, env=gh)
    refused_quietly = b.calls("sakura-launch") == []

    legacy = master_repo(b)
    master = b.tool("sakura-pr", "--print", cwd=legacy).stdout
    return {
        "the brief names the branch and the repo's default base": p.returncode == 0
        and "Branch: feature/tax  → base: main" in brief
        and "gh pr create --base main --title" in brief,
        "the commits since the base are in it, with their short hashes and bodies": all(
            f"{h} " in brief for h in shorts
        )
        and all(
            s in brief
            for s in (
                "round totals",
                "add the tax rate",
                "dev only change",
                "Two decimals, as the invoices print them.",
            )
        )
        and "initial price" not in brief,
        "the real diff is in it": all(
            l in brief
            for l in (
                "+TAX = 0.13",
                "+    return round(p * (1 + TAX), 2)",
                "+DEV_ONLY = 1",
                "app.py | 4 ++++",
            )
        ),
        "--base develop narrows the commits and the diff to what's after develop": "→ base: develop"
        in dev
        and "gh pr create --base develop --title" in dev
        and "+TAX = 0.13" in dev
        and "add the tax rate" in dev
        and "dev only change" not in dev
        and "+DEV_ONLY = 1" not in dev,
        "the default base is whatever gh says the repo's is": "→ base: develop"
        in gh_says
        and "dev only change" not in gh_says,
        "without gh the base is still found from the repo": "→ base: main" in no_gh
        and "+TAX = 0.13" in no_gh,
        "a repo on master, with no gh, is compared against master": "feat  → base: master"
        in master
        and "add b on feat" in master
        and "+B_ON_FEAT = 2" in master
        and "first on master" not in master,
        "an unpushed branch is told to push first; a pushed one isn't": "git push -u origin feature/tax"
        in brief
        and "isn't fully pushed" not in pushed,
        "--draft, or the word, opens a draft": all(
            "Open it as a draft." in t and "--body-file FILE --draft" in t
            for t in (draft, worded)
        )
        and "--draft" not in brief
        and "From me: draft mention the rounding" in worded,
        "an existing PR is edited, not opened twice": "https://github.com/acme/shop/pull/41"
        in existing
        and "gh pr edit" in existing
        and "gh pr edit" not in brief,
        "the repo's PR template and recent PRs are handed over for the style": "Checklist-7c1"
        in templated
        and "Speed up checkout" in styled,
        "uncommitted work is called out, not folded in": "Uncommitted changes exist"
        in templated
        and "not committed" not in templated
        and "Uncommitted" not in brief,
        "--print stops there: the model isn't started": printed_only,
        "--exec and the plain run hand exactly that brief to sakura-launch": ex.returncode
        == 0
        and tui.returncode == 0
        and len(launched) == 2
        and launched[0]["argv"]
        == ["--exec", "--skip-git-repo-check", brief.rstrip("\n")]
        and launched[1]["argv"] == [brief.rstrip("\n")]
        and os.path.realpath(launched[0]["cwd"]) == os.path.realpath(work),
        "the tool itself only reads from gh: it never creates, edits or comments": gh_verbs
        != set()
        and gh_verbs <= {"repo view", "pr list"},
        "a branch named like a command stays a name": not ran
        and hostile.returncode == 0
        and "x$(touch${IFS}pwned)" in hostile.stdout,
        "on the base branch, or on no branch, it refuses and starts nothing": on_base.returncode
        != 0
        and "make a branch first" in on_base.stderr
        and detached.returncode != 0
        and "not on a branch" in detached.stderr
        and refused_quietly,
    }


def review(tmp):
    b = Box(tmp)
    b.fake("gh", GH)
    b.fake("sakura-launch", LAUNCH)
    work = shop_repo(b)[1]
    pr_diff = "diff --git a/cart.py b/cart.py\n--- a/cart.py\n+++ b/cart.py\n@@ -1 +1,2 @@\n items = []\n+LIMIT_FROM_THE_PR = 50\n"
    gh = {
        "FAKE_GH_DEFAULT": "main",
        "FAKE_GH_DIFF": pr_diff,
        "FAKE_GH_META": "# Limit the cart  (#7, by ana, cart-limit → main, +1 -0, 1 files)\n\nStops carts over fifty items.\n",
    }

    b.git(work, "checkout", "-q", "main")
    clean = b.tool("sakura-review", "--exec", cwd=work, env=gh)
    clean_started = b.calls("sakura-launch")
    b.git(work, "checkout", "-q", "feature/tax")

    write(os.path.join(work, "app.py"), "UNCOMMITTED = 1\n", "a")
    local = b.tool("sakura-review", "--print", cwd=work, env=gh).stdout
    write(os.path.join(work, "staged.txt"), "STAGED_LINE\n")
    b.git(work, "add", "staged.txt")
    staged = b.tool("sakura-review", "--print", "--staged", cwd=work, env=gh).stdout
    rng = b.tool(
        "sakura-review",
        "--print",
        "main..develop",
        "look",
        "at",
        "naming",
        cwd=work,
        env=gh,
    ).stdout

    b.clear()
    by_number = b.tool("sakura-review", "--print", "7", cwd=work, env=gh).stdout
    asked_7 = [c["argv"] for c in b.calls("gh")]
    post = b.tool("sakura-review", "--print", "7", "--post", cwd=work, env=gh).stdout
    b.clear()
    url = "https://github.com/acme/other/pull/12"
    by_url = b.tool("sakura-review", "--print", url + "/files", cwd=work, env=gh).stdout
    by_anchor = b.tool(
        "sakura-review", "--print", url + "#discussion_r99", "--post", cwd=work, env=gh
    ).stdout
    asked_url = [c["argv"] for c in b.calls("gh")]
    empty_pr = b.tool(
        "sakura-review", "--print", "8", cwd=work, env={"FAKE_GH_DEFAULT": "main"}
    )

    b.clear()
    ex = b.tool("sakura-review", "--exec", "7", "--post", cwd=work, env=gh)
    tui = b.tool("sakura-review", "7", cwd=work, env=gh)
    launched = b.calls("sakura-launch")
    gh_verbs = verbs(b)

    legacy = master_repo(b)
    master = b.tool("sakura-review", "--print", cwd=legacy)
    return {
        "with nothing named, it's the branch against the base, uncommitted work included": "this branch against main"
        in local
        and all(
            l in local for l in ("+TAX = 0.13", "+DEV_ONLY = 1", "+UNCOMMITTED = 1")
        )
        and "read around every hunk" in local,
        "--staged is the staged diff only": "the staged changes" in staged
        and "+STAGED_LINE" in staged
        and "UNCOMMITTED" not in staged
        and "TAX = 0.13" not in staged,
        "a range is that range, and words after it steer the review": "the range main..develop"
        in rng
        and "+DEV_ONLY = 1" in rng
        and "TAX" not in rng
        and "From me: look at naming" in rng,
        "a PR number is read through gh: its description and its diff": "Review pull request #7."
        in by_number
        and "+LIMIT_FROM_THE_PR = 50" in by_number
        and "Stops carts over fifty items." in by_number
        and ["pr", "diff", "7"] in asked_7
        and any(a[:3] == ["pr", "view", "7"] for a in asked_7),
        "the local diff isn't mixed into a PR's review": "UNCOMMITTED" not in by_number
        and "TAX = 0.13" not in by_number,
        "without --post the brief says not to post, and names no posting command": "don't post anything to the PR"
        in by_number
        and "gh pr comment" not in by_number,
        "with --post it's one comment on that PR, no approval": "gh pr comment 7 --body-file FILE"
        in post
        and "Don't approve or request changes" in post
        and "don't post anything" not in post,
        "a pasted URL ending in /files or an anchor still means that PR, in its own repo": "Review pull request #12."
        in by_url
        and ["pr", "diff", url] in asked_url
        and all(
            a[2] == url for a in asked_url if a[:2] in (["pr", "view"], ["pr", "diff"])
        )
        and f"gh pr comment {url} --body-file FILE" in by_anchor,
        "a PR with no diff is said so, exit non-zero": empty_pr.returncode != 0
        and "nothing to review in pull request #8" in empty_pr.stderr,
        "nothing to review starts nothing": clean.returncode != 0
        and "nothing to review" in clean.stderr
        and clean_started == [],
        "--exec and the plain run hand the brief to sakura-launch": ex.returncode == 0
        and tui.returncode == 0
        and len(launched) == 2
        and launched[0]["argv"]
        == ["--exec", "--skip-git-repo-check", post.rstrip("\n")]
        and launched[1]["argv"] == [by_number.rstrip("\n")],
        "the tool itself only reads from gh, --post or not": gh_verbs != set()
        and gh_verbs <= {"repo view", "pr view", "pr diff"},
        "a repo on master, with no gh, is reviewed against master": master.returncode
        == 0
        and "this branch against master" in master.stdout
        and "+B_ON_FEAT = 2" in master.stdout,
    }


# ── sakura-try ───────────────────────────────────────────────────────────────


def try_(tmp):
    b = Box(tmp)
    # The session: it notes where it was put and what was there, leaves a file behind, and ends as it's told to.
    b.fake(
        "sakura-launch",
        'record(listing=sorted(os.listdir(".")))\nopen("scratch.py", "w").write("print(1)\\n")\nsys.exit(int(os.environ.get("FAKE_LAUNCH_RC", "0")))',
    )
    shell = b.fake(
        "a-shell",
        'record(listing=sorted(os.listdir(".")))\nopen("left-behind", "w").write("x")',
    )
    cache = os.path.join(b.env["XDG_CACHE_HOME"], "sakura-try")
    repo = os.path.join(b.root, "shop")
    os.makedirs(repo)
    write(os.path.join(repo, "composer.json"), "{}\n")
    write(os.path.join(repo, "index.php"), "<?php\n")
    before = tree(repo)

    r = b.tool(
        "sakura-try",
        "does",
        "array_map",
        "keep",
        "keys",
        cwd=repo,
        env={"FAKE_LAUNCH_RC": "3"},
    )
    first = b.calls("sakura-launch")
    left_1 = os.listdir(cache) if os.path.isdir(cache) else None
    b.tool("sakura-try", "rust", "is", "go", "faster", "than", "python", cwd=repo)
    b.tool("sakura-try", "is", "go", "faster", "than", "rust", cwd=repo)
    asked = b.calls("sakura-launch")
    b.clear()
    sh = b.tool("sakura-try", cwd=repo, env={"SHELL": shell})
    shells = b.calls("a-shell")
    started = b.calls("sakura-launch")
    left_2 = os.listdir(cache) if os.path.isdir(cache) else None
    after = tree(repo)

    langs = {}
    for manifest, lang in (
        ("package.json", "node"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
        ("pyproject.toml", "python"),
        ("notes.txt", "bash"),
    ):
        d = os.path.join(b.root, "proj-" + lang)
        os.makedirs(d)
        write(os.path.join(d, manifest), "")
        b.clear()
        b.tool("sakura-try", "will", "it", "work", cwd=d)
        got = b.calls("sakura-launch")
        langs[lang] = bool(got) and got[0]["argv"][0].startswith(
            f"Scratch question, in {lang}: will it work"
        )
    where = os.path.realpath(first[0]["cwd"]) if first else ""
    brief = first[0]["argv"][0] if first else ""
    return {
        "the session starts in a new, empty directory under the cache": len(first) == 1
        and os.path.dirname(where) == os.path.realpath(cache)
        and first[0]["listing"] == [],
        "the brief has the question, the repo's language and where the repo is": brief.startswith(
            "Scratch question, in php: does array_map keep keys"
        )
        and os.path.realpath(repo) in brief
        and where in brief
        and len(first[0]["argv"]) == 1,
        "the scratch directory is gone when the session ends": left_1 == []
        and not os.path.exists(where),
        "the session's exit status is the tool's": r.returncode == 3,
        "a language as the first word wins over the repo's": len(asked) == 3
        and asked[1]["argv"][0].startswith(
            "Scratch question, in rust: is go faster than python"
        ),
        "a language's name inside the question stays in the question": len(asked) == 3
        and asked[2]["argv"][0].startswith(
            "Scratch question, in php: is go faster than rust"
        ),
        "with no words it opens your shell there, no model, and cleans up after": sh.returncode
        == 0
        and len(shells) == 1
        and started == []
        and os.path.dirname(os.path.realpath(shells[0]["cwd"]))
        == os.path.realpath(cache)
        and shells[0]["listing"] == []
        and left_2 == [],
        "nothing is left in the repo, and nothing in it changed": after == before,
        "the language comes from the manifest: node, rust, go, python, else bash": all(
            langs.values()
        )
        and len(langs) == 5,
    }


# ── hear ─────────────────────────────────────────────────────────────────────

UV = """record(audio_was_there=os.path.isfile(argv[-2]) if len(argv) > 1 else False)
if os.environ.get("FAKE_UV_RC"):
    sys.stderr.write("ModuleNotFoundError: faster_whisper went missing\\n")
    sys.exit(int(os.environ["FAKE_UV_RC"]))
if os.environ.get("FAKE_TRANSCRIPT"):
    sys.stdout.write(open(os.environ["FAKE_TRANSCRIPT"]).read())
"""
# A recorder writes the file it was given and keeps recording until it's stopped.
RECORDER = """record()
if os.environ.get("FAKE_MIC_DEAD"):
    sys.exit(1)
open(argv[-1], "wb").write(b"RIFF" + b"\\0" * 60)
import time
time.sleep(30)
"""


def hear(tmp):
    b = Box(tmp)
    b.fake("uv", UV)
    b.fake("pw-record", RECORDER)
    b.fake("sakura-launch", LAUNCH)
    said = "We ship the importer on Friday the 13th at 3pm. Ravi owns the rollback plan. Decision: no schema change this sprint."
    transcript = write(os.path.join(b.root, "transcript.txt"), said + "\n")
    wav = write(os.path.join(b.root, "meeting.wav"), b"RIFF" + b"\0" * 60, "wb")
    env = {"FAKE_TRANSCRIPT": transcript}
    cache = b.env["HOME"] + "/.cache"

    plain = b.tool("hear", wav, env=env)
    file_calls = b.calls()
    b.clear()
    b.tool("hear", "--model", "tiny", wav, env=env)
    b.tool("hear", wav, env=dict(env, SAKURA_WHISPER_MODEL="base"))
    sizes = [c["argv"][-1] for c in b.calls("uv")]

    b.clear()
    started = time.time()
    timed = b.tool("hear", "1", env=env, timeout=60)
    took = time.time() - started
    rec = b.calls("pw-record")
    heard = b.calls("uv")
    left = (
        [n for n in os.listdir(cache) if n.startswith("hear-")]
        if os.path.isdir(cache)
        else []
    )

    b.clear()
    typo = b.tool("hear", "meetng.wav", env=env, timeout=60)
    typo_calls = b.calls()
    dead = b.tool("hear", "1", env=dict(env, FAKE_MIC_DEAD="1"), timeout=60)
    dead_heard = b.calls("uv")

    b.clear()
    notes = b.tool("hear", "--notes", wav, env=env)
    launched = b.calls("sakura-launch")
    b.clear()
    silent = b.tool("hear", "--notes", wav)
    silent_launched = b.calls("sakura-launch")
    failed = b.tool("hear", wav, env={"FAKE_UV_RC": "1"})

    b.unfake("pw-record")
    b.fake("arecord", RECORDER)
    b.clear()
    b.tool("hear", "1", env=env, timeout=60)
    alsa = b.calls("arecord")
    b.unfake("arecord")
    b.clear()
    no_mic = b.tool("hear", "1", env=env, timeout=60)
    no_mic_heard = b.calls("uv")
    b.unfake("uv")
    no_uv = b.tool("hear", wav, env=env)
    uv_argv = file_calls[0]["argv"] if file_calls else []
    brief = launched[0]["argv"][0] if launched else ""
    return {
        "a recording's transcript is printed, and only that": plain.returncode == 0
        and plain.stdout == said + "\n",
        "the file goes to faster-whisper through uv, with the default model, and nothing is recorded": [
            c["prog"] for c in file_calls
        ]
        == ["uv"]
        and uv_argv[:5] == ["run", "-q", "--with", "faster-whisper", "--with"]
        and uv_argv[-2:] == [wav, "small"]
        and file_calls[0]["audio_was_there"],
        "--model and SAKURA_WHISPER_MODEL choose the model": sizes == ["tiny", "base"],
        "hear 1 records for a second at 16 kHz mono into the cache, then stops the recorder": timed.returncode
        == 0
        and timed.stdout == said + "\n"
        and took < 15
        and len(rec) == 1
        and rec[0]["argv"][:4] == ["--rate", "16000", "--channels", "1"]
        and os.path.dirname(rec[0]["argv"][-1]) == cache,
        "what was recorded is what's transcribed, and the recording is deleted after": len(
            heard
        )
        == 1
        and len(rec) == 1
        and heard[0]["argv"][-2] == rec[0]["argv"][-1]
        and heard[0]["audio_was_there"]
        and left == [],
        "arecord is used when it's the recorder there is": len(alsa) == 1
        and alsa[0]["argv"][:7] == ["-q", "-f", "S16_LE", "-r", "16000", "-c", "1"],
        "a mistyped file name is an error, not a recording from the microphone": typo.returncode
        != 0
        and "meetng.wav" in typo.stderr
        and typo_calls == [],
        "a recorder that wrote nothing is said so, and nothing is transcribed": dead.returncode
        != 0
        and "microphone" in dead.stderr
        and dead_heard == [],
        "--notes hands the whole transcript to Sakura, asking for notes, decisions and pa remind": notes.returncode
        == 0
        and len(launched) == 1
        and len(launched[0]["argv"]) == 1
        and brief.endswith("Transcript:\n" + said)
        and "pa remind" in brief
        and "decisions" in brief
        and "action items" in brief,
        "--notes with nothing heard starts nothing, exit 1": silent.returncode == 1
        and silent_launched == []
        and "nothing heard" in silent.stderr,
        "a failed transcription is exit non-zero with the engine's last words": failed.returncode
        != 0
        and "transcription failed" in failed.stderr
        and "faster_whisper went missing" in failed.stderr
        and failed.stdout == "",
        "no recorder: it names the three it looks for and what to install": no_mic.returncode
        != 0
        and no_mic_heard == []
        and all(
            w in no_mic.stderr
            for w in ("pw-record", "parecord", "arecord", "apt-get install")
        ),
        "no uv: it names uv and how to install it": no_uv.returncode != 0
        and "uv isn't installed" in no_uv.stderr
        and "astral.sh/uv/install.sh" in no_uv.stderr,
    }


# ── say ──────────────────────────────────────────────────────────────────────

PIPER = """data = sys.stdin.buffer.read()
record(stdin=data.decode("utf-8"))
if os.environ.get("FAKE_PIPER_RC"):
    sys.exit(int(os.environ["FAKE_PIPER_RC"]))
sys.stdout.buffer.write(b"PCM:" + data)
"""
PLAYER = 'record(stdin=sys.stdin.buffer.read().decode("utf-8"))'
CURL = """record()
out, url = argv[argv.index("-o") + 1], argv[-1]
if os.environ.get("FAKE_CURL_FAILS_ON") and url.endswith(os.environ["FAKE_CURL_FAILS_ON"]):
    open(out, "w").write("half a file")
    sys.exit(22)
open(out, "w").write('{"audio": {"sample_rate": 16000, "quality": "low"}}' if url.endswith(".json") else "a voice")
"""


def say(tmp):
    b = Box(tmp)
    voices = os.path.join(b.env["XDG_DATA_HOME"], "piper")

    def voice(name, rate):
        write(os.path.join(voices, name + ".onnx"), "a voice")
        write(
            os.path.join(voices, name + ".onnx.json"),
            json.dumps(
                {
                    "audio": {"sample_rate": rate, "quality": "medium"},
                    "espeak": {"voice": "en-us"},
                }
            ),
        )

    voice("en_US-lessac-medium", 22050)
    voice("en_GB-alan-low", 16000)
    for name, body in (
        ("piper", PIPER),
        ("aplay", PLAYER),
        ("curl", CURL),
        ("espeak-ng", "record()"),
    ):
        b.fake(name, body)

    r = b.tool("say", "the build is", "green")
    c1 = b.calls()
    b.clear()
    b.run(["bash", "-c", f"echo 'from a pipe' | {BIN}/say"])
    piped = b.calls("piper")
    b.clear()
    b.tool("say", "--voice", "en_GB-alan-low", "slower voice")
    b.tool("say", "by default", env={"SAKURA_VOICE": "en_GB-alan-low"})
    low = b.calls()
    b.clear()
    hush = b.tool("say", stdin="")
    hush_calls = b.calls()

    b.clear()
    fetched = b.tool("say", "--voice", "ne_NP-google-x_low", "नमस्ते")
    got = b.calls()
    b.clear()
    half = b.tool(
        "say",
        "--voice",
        "de_DE-thorsten-high",
        "hallo",
        env={"FAKE_CURL_FAILS_ON": ".json"},
    )
    half_calls = b.calls()
    half_left = [n for n in os.listdir(voices) if n.startswith("de_DE")]

    b.clear()
    broken = b.tool("say", "piper broke", env={"FAKE_PIPER_RC": "1"})
    broken_calls = b.calls()

    b.fake("pw-play", PLAYER)
    b.fake("paplay", PLAYER)
    b.clear()
    b.tool("say", "through pipewire")
    pw = b.calls()
    b.unfake("pw-play")
    b.clear()
    b.tool("say", "through pulse")
    pulse = b.calls()

    # No piper on PATH, but one in ~/.local/bin: what a timer or a cron job sees.
    b.unfake("piper")
    b.unfake("paplay")
    b.fake("piper", PIPER, where=os.path.join(b.home, ".local", "bin"))
    b.clear()
    home_piper = b.tool("say", "from the home bin")
    home_calls = b.calls()
    os.unlink(os.path.join(b.home, ".local", "bin", "piper"))

    b.fake("spd-say", "record()")
    b.clear()
    spd = b.tool("say", "-dashing", "text")
    spd_calls = b.calls()
    b.unfake("spd-say")
    b.clear()
    esp = b.tool("say", "last resort")
    esp_calls = b.calls()
    b.unfake("espeak-ng")
    b.clear()
    none = b.tool("say", "anyone?")
    none_calls = b.calls()

    def of(calls, prog):
        return next(
            (c for c in calls if c["prog"] == prog), {"argv": [], "stdin": None}
        )

    hf = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ne/ne_NP/google/x_low/ne_NP-google-x_low.onnx"
    return {
        "the words go to piper on stdin, with the default voice's model": r.returncode
        == 0
        and of(c1, "piper")["stdin"] == "the build is green\n"
        and of(c1, "piper")["argv"]
        == [
            "--model",
            os.path.join(voices, "en_US-lessac-medium.onnx"),
            "--output-raw",
        ],
        "what piper makes is what the player plays, as 16-bit mono at the voice's rate": of(
            c1, "aplay"
        )["stdin"]
        == "PCM:the build is green\n"
        and of(c1, "aplay")["argv"] == ["-q", "-r", "22050", "-f", "S16_LE", "-c", "1"]
        and [c["prog"] for c in c1] in (["piper", "aplay"], ["aplay", "piper"]),
        "`cmd | say` speaks a command's output": len(piped) == 1
        and piped[0]["stdin"] == "from a pipe\n",
        "--voice and SAKURA_VOICE choose the voice": [
            c["argv"][1] for c in low if c["prog"] == "piper"
        ]
        == [os.path.join(voices, "en_GB-alan-low.onnx")] * 2,
        "a 16 kHz voice is played at 16 kHz": [
            c["argv"][2] for c in low if c["prog"] == "aplay"
        ]
        == ["16000", "16000"],
        "nothing to say is exit 0 and no engine runs": hush.returncode == 0
        and hush_calls == [],
        "a voice that isn't here is fetched once, from its place in piper-voices, then spoken": fetched.returncode
        == 0
        and [c["argv"][-1] for c in got if c["prog"] == "curl"] == [hf, hf + ".json"]
        and of(got, "piper")["stdin"] == "नमस्ते\n"
        and of(got, "piper")["argv"][1]
        == os.path.join(voices, "ne_NP-google-x_low.onnx")
        and of(got, "aplay")["argv"][2] == "16000",
        "a fetch that fails leaves no half voice and falls back to the next engine": half.returncode
        == 0
        and half_left == []
        and "couldn't fetch the voice de_DE-thorsten-high" in half.stderr
        and of(half_calls, "espeak-ng")["argv"] == ["--", "hallo"]
        and not any(c["prog"] == "piper" for c in half_calls),
        "when piper fails, silence isn't counted as spoken: the next engine speaks": broken.returncode
        == 0
        and of(broken_calls, "espeak-ng")["argv"] == ["--", "piper broke"],
        "pw-play is preferred, then paplay, then aplay": of(pw, "pw-play")["argv"]
        == ["--rate", "22050", "--format", "s16", "--channels", "1", "-"]
        and of(pw, "pw-play")["stdin"] == "PCM:through pipewire\n"
        and not any(c["prog"] in ("paplay", "aplay") for c in pw)
        and of(pulse, "paplay")["argv"]
        == ["--raw", "--rate=22050", "--format=s16le", "--channels=1"]
        and not any(c["prog"] == "aplay" for c in pulse),
        "a piper in ~/.local/bin is used when that isn't on PATH": home_piper.returncode
        == 0
        and of(home_calls, "piper")["stdin"] == "from the home bin\n"
        and of(home_calls, "aplay")["stdin"] == "PCM:from the home bin\n"
        and not any(c["prog"] == "espeak-ng" for c in home_calls),
        "without piper, speech-dispatcher speaks, and text starting with a dash is still text": spd.returncode
        == 0
        and [(c["prog"], c["argv"]) for c in spd_calls]
        == [("spd-say", ["-w", "--", "-dashing text"])],
        "without that, espeak-ng": esp.returncode == 0
        and [(c["prog"], c["argv"]) for c in esp_calls]
        == [("espeak-ng", ["--", "last resort"])],
        "with no engine at all it's exit 1 and names three to install": none.returncode
        == 1
        and none_calls == []
        and all(
            w in none.stderr for w in ("piper-tts", "speech-dispatcher", "espeak-ng")
        ),
    }


# ── sakura-red ───────────────────────────────────────────────────────────────


def red(tmp):
    """Only what isn't the model: which command runs the tests here, test or sentence, and what's handed over."""
    b = Box(tmp)
    b.fake("sakura-launch", LAUNCH)
    how = {}
    for manifest, text, cmd in (
        ("Makefile", "build:\n\ttrue\ntest:\n\tpytest\n", "make test"),
        ("package.json", "{}", "npm test"),
        ("pyproject.toml", "", "python3 -m pytest -q"),
        ("Cargo.toml", "", "cargo test"),
        ("go.mod", "", "go test ./..."),
        ("composer.json", "{}", "php artisan test"),
    ):
        d = os.path.join(b.root, "red-" + manifest)
        os.makedirs(d)
        write(os.path.join(d, manifest), text)
        how[cmd] = (
            f"How tests run here: {cmd}."
            in b.tool(
                "sakura-red", "--print", "tests/test_price.py::test_tax", cwd=d
            ).stdout
        )
    d = os.path.join(b.root, "red-empty")
    os.makedirs(d)
    a_test = b.tool(
        "sakura-red", "--print", "tests/test_price.py::test_tax", cwd=d
    ).stdout
    sentence = b.tool(
        "sakura-red", "--print", "total() should round to 2 decimals", cwd=d
    ).stdout
    told = b.tool(
        "sakura-red", "--print", "--cmd", "tox -e py", "tests/test_price.py", cwd=d
    ).stdout
    none = b.tool("sakura-red", cwd=d)
    printed_only = b.calls("sakura-launch") == []
    b.tool("sakura-red", "--exec", "tests/test_price.py::test_tax", cwd=d)
    b.tool("sakura-red", "tests/test_price.py::test_tax", cwd=d)
    launched = [c["argv"] for c in b.calls("sakura-launch")]
    return {
        "the test command comes from the repo's manifest": all(how.values())
        and len(how) == 6,
        "with no manifest it's told to work the command out, and --cmd overrides": "work out how tests run here"
        in a_test
        and "How tests run here: tox -e py." in told,
        "a test id is made to pass; a sentence becomes a test first": a_test.startswith(
            "Make this failing test pass: tests/test_price.py::test_tax"
        )
        and sentence.startswith(
            "Test-first: write a test for this, watch it fail, then make it pass: total() should round to 2 decimals"
        )
        and "First write the test" in sentence
        and "First write the test" not in a_test,
        "the rules go with it: the test isn't weakened, the diff stays small": all(
            "don't loosen the assertion or skip the test" in t
            and "no drive-by refactors" in t
            for t in (a_test, sentence)
        ),
        "--print and no words start nothing; --exec and the plain run hand over that brief": none.returncode
        == 2
        and printed_only
        and launched
        == [
            ["--exec", "--skip-git-repo-check", a_test.rstrip("\n")],
            [a_test.rstrip("\n")],
        ],
    }


CASES = {
    "clip": clip,
    "decide": decide,
    "morning": morning,
    "mail": mail,
    "fmt": fmt,
    "watch": watch,
    "pr": pr,
    "review": review,
    "try": try_,
    "hear": hear,
    "say": say,
    "red": red,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    total = passed = skipped = 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                results = fn(tmp)
            except Exception as e:  # a crash is a failure with a reason, not a stack trace in the summary
                results = {f"{name} ran without crashing": False}
                print(f"  {name}: {type(e).__name__}: {e}")
        for check, ok in results.items():
            if ok is SKIP:
                skipped += 1
                print(f"  SKIP  {name}: {check}")
                continue
            total += 1
            passed += bool(ok)
            print(f"  {'PASS' if ok else 'FAIL'}  {name}: {check}")
    print(
        f"\n{passed}/{total}"
        + (f", {skipped} skipped (not proven on this machine)" if skipped else "")
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
