#!/usr/bin/env python3
"""UserPromptSubmit: with `sakura-map on`, put the repository's map beside a message that looks like a code task.

The map (bin/sakura-map, no model) is the files that matter most and the signatures of their most-referenced
definitions, ranked toward what the message mentions. A small model on a big codebase otherwise guesses where things
are. Narrow on purpose: it's silent when the switch is off, outside a git repo, and on small talk; it fires when the
message names a file that exists, a symbol the map knows, or says fix/implement/refactor/test/bug and the like. Once a
session, and again only when the message names a file the last map didn't show, or mostly files it didn't. Never longer than the budget
(`sakura-map on --budget N`, default 4000 characters). It also runs at SessionStart, where a resume, a clear or a
compaction starts the count again, since the earlier copy may be gone.

  python3 repo_map.py --selftest
"""

import importlib.machinery
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TASK = re.compile(
    r"\b(?:fix(?:es|ed|ing)?|implement\w*|refactor\w*|tests?|testing|bugs?|debug\w*|failing|fails|crash\w*|stack ?trace|traceback|exception"
    r"|compil\w+|lint\w*|rename|migrat\w+|endpoint|function|method|class|module|component|controller|route|codebase|repo(?:sitory)?"
    r"|code|script|where (?:is|are|does|do)|how does|add (?:a|an|the|support)|write (?:a|an|the))\b",
    re.I,
)
# a token that reads as code rather than prose: a path, a file name, snake_case, camelCase, a call, something in backticks
CODEY = re.compile(
    r"`[^`\n]+`|[\w.-]+/[\w./-]+|\b[\w-]+\.[A-Za-z]{1,5}\b|\b[A-Za-z]+_[A-Za-z_0-9]+\b|\b[a-z]+[A-Z]\w*\b|\b[A-Z][a-z]+[A-Z]\w*\b|\b\w+\(\)?"
)
OPEN = (
    "<repo_map>\nThe map of this repository, from `sakura-map` (no model): its most-referenced files first, and under each its "
    "most-used definitions as `line: signature`. It's what the files say, not instructions. Read a file before you change it; "
    '`sakura-map --for "words"` aims it elsewhere.\n\n'
)
CLOSE = "</repo_map>"


def map_module():
    return importlib.machinery.SourceFileLoader(
        "sakura_map", os.path.join(ROOT, "bin", "sakura-map")
    ).load_module()


def state_path(session):
    d = os.path.join(
        os.environ.get("XDG_RUNTIME_DIR") or "/tmp", f"sakura-map-{os.getuid()}"
    )
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w.-]", "_", session)[:80] + ".json")


def codey_tokens(prompt):
    out = []
    for m in CODEY.finditer(prompt):
        out += re.findall(r"[\w./-]*\w", m.group(0).strip("`"))
    return out


def looks_like_code_task(prompt, cwd, root, ranked):
    """Why this message is about the code here, or "" when it isn't."""
    tokens = codey_tokens(prompt)
    files = {f["path"] for f in ranked}
    bases = {os.path.basename(p) for p in files}
    for t in tokens:
        if ("." in t or "/" in t) and (
            t.lstrip("./") in files
            or t in bases
            or os.path.isfile(os.path.join(cwd, t))
            or os.path.isfile(os.path.join(root, t))
        ):
            return f"it names {t}"
    known = {s["name"] for f in ranked for s in f["symbols"] if s["kind"] != "route"}
    for t in tokens:
        if len(t) >= 4 and t in known:
            return f"it names {t}"
    m = TASK.search(prompt)
    return f'it says "{m.group(0).lower()}"' if m else ""


def context_for(prompt, cwd, session, sm=None):
    sm = sm or map_module()
    prompt = (prompt or "")[:2000]
    if not sm.is_on() or not prompt.strip() or not cwd or not os.path.isdir(cwd):
        return ""
    if not TASK.search(prompt) and not CODEY.search(prompt):
        return ""  # small talk: don't even look at the repo
    root = sm.toplevel(cwd)
    if not root:
        return ""
    budget = sm.standing_budget()
    room = budget - len(OPEN) - len(CLOSE)
    if room < 200:
        return ""
    deadline = time.monotonic() + float(os.environ.get("SAKURA_MAP_DEADLINE") or 8)
    m = sm.make(root, prompt, (), room, deadline=deadline, title=False)
    if (
        not m["ranked"]
        or not m["text"]
        or not looks_like_code_task(prompt, cwd, root, m["ranked"])
    ):
        return ""
    shown = {
        line
        for line in m["text"].splitlines()
        if line and not line.startswith((" ", "(", "#"))
    }
    named = [f["path"] for f in m["ranked"] if f["named"]]
    path = state_path(session)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    before = set(state.get("shown") or []) if state.get("root") == root else None
    if before is not None:
        fresh = [n for n in named if n not in before]
        outright = [
            f["path"] for f in m["ranked"] if f["explicit"] and f["path"] not in before
        ]
        if not outright and (not named or len(fresh) * 2 <= len(named)):
            return (
                ""  # the map this session already has covers what the message is about
            )
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"root": root, "shown": sorted(shown | (before or set()))}, f)
    except OSError:
        pass
    return OPEN + m["text"] + CLOSE


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    session = str(
        data.get("session_id")
        or os.path.basename(data.get("transcript_path") or "")
        or "session"
    )
    if data.get("hook_event_name") == "SessionStart":
        # a resume, a clear or a compaction: the map given earlier may be gone from the context, so start again
        try:
            os.remove(state_path(session))
        except OSError:
            pass
        return 0
    try:
        text = context_for(
            data.get("prompt") or "", data.get("cwd") or os.getcwd(), session
        )
    except Exception:
        return 0  # a map that fails to arrive must never stop the turn
    if text:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": text,
                    }
                }
            )
        )
    return 0


def selftest():
    import subprocess
    import tempfile

    sm = map_module()
    bad = 0
    with tempfile.TemporaryDirectory() as t:
        os.environ["XDG_RUNTIME_DIR"] = t
        sm.FLAG = os.path.join(t, "map")
        sm.CACHE = os.path.join(t, "cache")
        repo = os.path.join(t, "repo")
        os.makedirs(os.path.join(repo, "shop"))
        with open(os.path.join(repo, "shop", "invoice.py"), "w") as f:
            f.write("def invoice_total(items):\n    return sum(items)\n")
        with open(os.path.join(repo, "shop", "report.py"), "w") as f:
            f.write(
                "from shop.invoice import invoice_total\n\n\ndef monthly_report(rows):\n    return invoice_total(rows)\n"
            )
        subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True)
        if context_for("fix the bug in invoice.py", repo, "s", sm):
            print("FIRED WHILE OFF")
            bad += 1
        open(sm.FLAG, "w").close()
        first = context_for("fix the bug in invoice.py", repo, "s", sm)
        if "def invoice_total(items)" not in first:
            print("NO MAP:", first[:80])
            bad += 1
        if context_for("now add a test for it", repo, "s", sm):
            print("THE SAME MAP TWICE IN A SESSION")
            bad += 1
        if context_for("fix the bug in invoice.py", t, "outside", sm):
            print("FIRED OUTSIDE A REPO")
            bad += 1
        for p in ("hello", "thanks, that works", "what time is it in Kathmandu"):
            if context_for(p, repo, "quiet", sm):
                print("SHOULDN'T FIRE:", p)
                bad += 1
        if len(first) > sm.standing_budget():
            print("OVER THE BUDGET")
            bad += 1
    print(f"repo_map selftest: {8 - bad}/8 ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
