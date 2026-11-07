#!/usr/bin/env python3
"""UserPromptSubmit: asked what Sakura did, put the record beside the question, so the answer comes from it.

The model, asked "what did you do today?", dug through git log and find and answered "not a lot". A rule in AGENTS.md
didn't change that, so this hook runs sakura-recap itself when the question is about Sakura's own past work, and only
then: the patterns are narrow on purpose (a misfiring hook steers the model wrong).

  python3 recap_context.py --selftest
"""
import json
import os
import re
import subprocess
import sys

ASKS = re.compile(
    r"\bwhat\s+(?:did|have|has)\s+(?:you|sakura)\s+(?:do|done|change|changed|run|ran|touch|touched|fix|fixed|work(?:ed)?\s+on)\b"
    r"|\bwhat\s+(?:you|sakura)\s+(?:did|changed|ran)\b|\bwhat\s+changed\s+on\s+this\s+(?:box|machine)\b|^\s*\??recap\b"
    r"|\b(?:recap|summary|summarize|summarise|log)\s+of\s+(?:your|sakura'?s)\s+(?:work|day|session|changes)\b",
    re.I)
WHEN = (("yesterday", "yesterday"), ("this week", "week"), ("last week", "week"), ("past week", "week"), ("week", "week"))
RECAP = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "sakura-recap")


def when_of(prompt):
    p = prompt.lower()
    m = re.search(r"\b(?:last|past)\s+(\d+)\s+days?\b", p)
    if m:
        return f"{m.group(1)}d"
    m = re.search(r"\b(20\d\d-\d\d-\d\d)\b", p)
    if m:
        return m.group(1)
    for words, arg in WHEN:
        if words in p:
            return arg
    return "today"


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    prompt = data.get("prompt") or ""
    if not ASKS.search(prompt):
        return 0
    when = when_of(prompt)
    try:
        out = subprocess.run([sys.executable, RECAP, when], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return 0
    if len(out) > 6000:
        out = out[:2500] + "\n…\n" + out[-3000:]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
        f"<lookup>\nThe record of what you did ({when}), from `sakura-recap {when}`: the session transcripts and ?undo "
        "snapshots, not memory. Answer from this, briefly; don't search git or files for it. If it's empty, say so.\n\n"
        f"{out.strip()}\n</lookup>")}}))
    return 0


def selftest():
    bad = 0
    yes = ["what did you do today?", "What have you done since this morning", "what did sakura change yesterday",
           "recap", "?recap week", "what did you run on the server", "give me a recap of your work", "what changed on this box"]
    no = ["what did I do wrong here", "what does this function do", "do you know what changed in python 3.14",
          "fix the recap section of the README", "what did the test print", "how do I recap a meeting"]
    for p in yes:
        if not ASKS.search(p):
            print("SHOULD FIRE:", p); bad += 1
    for p in no:
        if ASKS.search(p):
            print("SHOULDN'T FIRE:", p); bad += 1
    for p, want in (("what did you do yesterday", "yesterday"), ("what did you change this week", "week"),
                    ("what did you do in the last 3 days", "3d"), ("what did you do on 2026-11-05", "2026-11-05"),
                    ("what did you do", "today")):
        if when_of(p) != want:
            print("WHEN WRONG:", p, when_of(p)); bad += 1
    total = len(yes) + len(no) + 5
    print(f"recap_context selftest: {total - bad}/{total} ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
