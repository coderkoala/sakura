#!/usr/bin/env python3
"""UserPromptSubmit: asked to write or answer a mail, put the user's learned voice beside the question.

`pa voice learn` counts how the user writes (greeting, sign-off, length, tone) from their own sent mail into a short
note. The model can't know to look for it, so this hook hands it over when the prompt is about drafting mail, and only
then. No note learned, no output. The note is at most 1200 characters and holds no mail text and no address.

  python3 voice_context.py --selftest
"""

import json
import os
import re
import subprocess
import sys

ASKS = re.compile(
    r"\b(?:draft|write|compose|reply|respond|answer|send|forward|reword|rewrite)\w*\b.{0,60}\b(?:e-?mails?|mail|inbox|message to|letter)\b"
    r"|\b(?:e-?mails?|mail|letter)\b.{0,40}\b(?:draft|reply|repl(?:y|ies)|respond|answer)\w*\b|\bin my (?:voice|style|tone)\b",
    re.I,
)
PA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "pa"
)


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if not ASKS.search(data.get("prompt") or ""):
        return 0
    try:
        note = subprocess.run(
            [sys.executable, PA, "voice"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return 0
    if not note.startswith("# How I write mail"):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        "<voice>\nHow the user writes mail, counted from their own sent mail (`pa voice`). Draft in this voice: their greeting, "
                        "their sign-off, their length and tone. It's a guide; what they ask for now wins. Show the draft before sending.\n\n"
                        + note[:1300]
                        + "\n</voice>"
                    ),
                }
            }
        )
    )
    return 0


def selftest():
    bad = 0
    yes = [
        "draft a reply to Sita's email about the invoice",
        "write an email to the landlord",
        "reply to that mail for me",
        "answer the newest message in my inbox",
        "that email from Ram needs a reply",
        "say no to the vendor, in my voice",
    ]
    no = [
        "how many unread emails do I have",
        "summarise my inbox",
        "write a python script",
        "reply with yes or no",
        "what does this error message mean",
        "draft the release notes",
    ]
    for p in yes:
        if not ASKS.search(p):
            print("SHOULD FIRE:", p)
            bad += 1
    for p in no:
        if ASKS.search(p):
            print("SHOULDN'T FIRE:", p)
            bad += 1
    total = len(yes) + len(no)
    print(f"voice_context selftest: {total - bad}/{total} ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
