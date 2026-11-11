#!/usr/bin/env python3
"""UserPromptSubmit: with `sakura-lean on`, put the tool-reference section a message is about beside that message.

The short reference (bin/sakura-lean) names every topic in one line; this delivers the full section when the user's
words match its commands' manuals, the way sakura-what matches them: no model, at most two sections a message, each
once per session. It also runs at SessionStart, where a resume, a clear or a compaction starts the count again, since
the earlier copy may be gone. With lean off it prints nothing, so the full AGENTS.md is never doubled.

  python3 tool_reference.py --selftest
"""

import importlib.machinery
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def lean_module():
    return importlib.machinery.SourceFileLoader(
        "sakura_lean", os.path.join(ROOT, "bin", "sakura-lean")
    ).load_module()


def state_path(session):
    d = os.path.join(
        os.environ.get("XDG_RUNTIME_DIR") or "/tmp", f"sakura-lean-{os.getuid()}"
    )
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w.-]", "_", session)[:80] + ".json")


def context_for(prompt, session, lean=None):
    lean = lean or lean_module()
    if not lean.is_on() or not prompt.strip():
        return ""
    path = state_path(session)
    try:
        with open(path, encoding="utf-8") as f:
            given = set(json.load(f))
    except (OSError, ValueError):
        given = set()
    new = [(t, b) for t, b, _ in lean.topics_for(prompt[:2000]) if t not in given]
    if not new:
        return ""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(given | {t for t, _ in new}), f)
    except OSError:
        pass
    return (
        "<reference>\nFrom the tool reference, the section"
        + ("s" if len(new) > 1 else "")
        + " this message is about. Use these commands "
        "rather than doing it by hand.\n\n"
        + "\n\n".join(f"## {t}\n\n{b}" for t, b in new)
        + "\n</reference>"
    )


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
        # a resume, a clear or a compaction: the sections given earlier may be gone from the context, so start again
        try:
            os.remove(state_path(session))
        except OSError:
            pass
        return 0
    try:
        text = context_for(data.get("prompt") or "", session)
    except Exception:
        return 0  # a reference that fails to arrive must never stop the turn
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
    import tempfile

    lean = lean_module()
    bad = 0
    with tempfile.TemporaryDirectory() as t:
        os.environ["XDG_RUNTIME_DIR"] = t
        lean.FLAG = os.path.join(t, "lean")
        if context_for("merge a.pdf and b.pdf into one pdf", "s", lean):
            print("FIRED WHILE OFF")
            bad += 1
        open(lean.FLAG, "w").close()
        first = context_for("merge a.pdf and b.pdf into one pdf", "s", lean)
        if "conv merge" not in first:
            print("NO conv SECTION:", first[:80])
            bad += 1
        if context_for("now split that pdf by pages", "s", lean):
            print("SAME SECTION TWICE IN A SESSION")
            bad += 1
        if "conv merge" not in context_for(
            "merge a.pdf and b.pdf into one pdf", "another", lean
        ):
            print("A NEW SESSION DIDN'T GET IT")
            bad += 1
        for p in ("hello", "thanks, that works", "refactor this function to be faster"):
            if context_for(p, "quiet", lean):
                print("SHOULDN'T FIRE:", p)
                bad += 1
    print(f"tool_reference selftest: {7 - bad}/7 ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
