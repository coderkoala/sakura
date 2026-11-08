#!/usr/bin/env python3
"""UserPromptSubmit: when the user points at the past ("like last time", "the way we did before", "that nginx fix"),
run sakura-recall for them and put the hits beside the question. The model never remembers past sessions by itself;
this makes the past arrive without being asked for by name.

Narrow on purpose, like recap_context: a misfiring hook steers the model wrong. It fires only on explicit
back-references, not on every question, and injects at most ~2000 characters.

  python3 recall_context.py --selftest
"""
import json
import os
import re
import subprocess
import sys

ASKS = re.compile(
    r"\b(?:like|same as|the way)\s+(?:we|you|i)\s+(?:did|used|had|fixed|set|do)\b"
    r"|\blast time\b(?!\s+(?:value|stamp|field|column|entry))|\bagain like\b|\bas before\b|\bthat .{0,40}\b(?:fix|command|trick|setup|error|config)\s+(?:from|we|you)\b"
    r"|\bwhat was that (?:command|fix|tool|setting)\b|\bremember (?:when|how) (?:we|you|i)\b|\bwe (?:did|had) this before\b",
    re.I)
STOPWORDS = {"like", "last", "time", "the", "way", "we", "you", "did", "used", "that", "what", "was", "again", "before",
             "same", "as", "when", "how", "remember", "a", "an", "it", "this", "me", "my", "to", "do", "fix", "and",
             "for", "with", "from", "please", "can", "could", "set", "up", "had", "i", "is", "in", "on", "of"}
RECALL = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "sakura-recall")


def terms_of(prompt):
    words = [w for w in re.findall(r"[\w.-]{3,}", prompt.lower()) if w not in STOPWORDS]
    return " ".join(words[:8])


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
    terms = terms_of(prompt)
    if not terms:
        return 0
    try:
        out = subprocess.run([sys.executable, RECALL, terms, "3"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return 0
    if not out.strip() or out.startswith("nothing in past sessions"):
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
        "<lookup>\nThe user is pointing at something from before. From `sakura-recall " + terms + "` (past sessions, shell "
        "history, decisions; may be out of date):\n\n" + out.strip()[:2000] + "\n</lookup>")}}))
    return 0


def selftest():
    bad = 0
    yes = ["fix nginx like we did last time", "set up the ssh tunnel the way you did before",
           "what was that command for the gpu reset", "remember how we fixed the swap?", "deploy it same as we did friday"]
    no = ["fix nginx", "what time is it", "set up ssh", "how do I remember my passwords", "do it again" ,
          "the last time value in the config is wrong", "like this: x = 1"]
    for p in yes:
        if not ASKS.search(p):
            print("SHOULD FIRE:", p); bad += 1
    for p in no:
        if ASKS.search(p):
            print("SHOULDN'T FIRE:", p); bad += 1
    t = terms_of("fix nginx like we did last time")
    if "nginx" not in t or "like" in t:
        print("TERMS WRONG:", t); bad += 1
    total = len(yes) + len(no) + 1
    print(f"recall_context selftest: {total - bad}/{total} ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
