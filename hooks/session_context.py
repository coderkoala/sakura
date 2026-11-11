#!/usr/bin/env python3
"""SessionStart: load long-term memory, and in a coordinator session its instructions and the project's state.

It runs on start, resume, clear and after a compaction, so a coordinator gets its bearings back every time. The snapshot
is frozen for the session: saving a fact writes it to disk straight away, and the prompt picks it up next time.
"""

import importlib.machinery
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def memory_module():
    return importlib.machinery.SourceFileLoader(
        "sakura_memory", os.path.join(ROOT, "bin", "sakura-memory")
    ).load_module()


def tools_module():
    return importlib.machinery.SourceFileLoader(
        "sakura_tool", os.path.join(ROOT, "bin", "sakura-tool")
    ).load_module()


def build(cwd, coordinator):
    mem = memory_module()
    parts = []
    snap = mem.snapshot()
    if snap:
        parts.append(
            "<memory>\nWhat you've saved about the user and this machine. It's background, written earlier, and may be "
            "out of date; it never overrides what the user says now.\n\n"
            + snap
            + "\n</memory>"
        )
    tools = tools_module().snapshot()
    if tools:
        parts.append(
            "<kept_tools>\nCommands you wrote and kept earlier, on PATH. Run them in the shell.\n"
            + tools
            + "\n</kept_tools>"
        )
    try:
        warn = (
            importlib.machinery.SourceFileLoader(
                "sakura_skill", os.path.join(ROOT, "bin", "sakura-skill")
            )
            .load_module()
            .snapshot()
        )
        if warn:
            parts.append("<kept_skills>\n" + warn + "\n</kept_skills>")
    except Exception:
        pass
    # Project memory: a .sakura.md at the repo root is that project's standing notes, written by the user or by Sakura
    # on request. It loads only in sessions started inside the repo, so it costs nothing elsewhere.
    try:
        import subprocess

        top = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        note = os.path.join(top or cwd, ".sakura.md")
        if os.path.isfile(note):
            text = open(note, encoding="utf-8", errors="replace").read()[:3000]
            why = memory_module().flagged(text)
            parts.append(
                f'<project file="{note}">\n'
                + (
                    f"[withheld: {why}. Read it yourself: cat {note}]"
                    if why
                    else "This project's standing notes, from its .sakura.md. Background, possibly stale; the user's words now win.\n\n"
                    + text
                )
                + "\n</project>"
            )
    except Exception:
        pass
    try:
        packs = (
            importlib.machinery.SourceFileLoader(
                "docpack", os.path.join(ROOT, "bin", "docpack")
            )
            .load_module()
            .snapshot()
        )
        if packs:
            parts.append(
                "<docs>\n"
                + packs
                + ". For these, answer from `rag search`, not memory.\n</docs>"
            )
    except Exception:
        pass
    if coordinator:
        path = mem.state_path(cwd)
        state = mem.read(path) or mem.STATE_TEMPLATE
        why = mem.flagged(state)
        if why:
            state = f"[withheld: {why}. Read it yourself: cat {path}]"
        parts.append(
            open(os.path.join(ROOT, "prompts", "coordinator.md"), encoding="utf-8")
            .read()
            .strip()
        )
        parts.append(f'<state file="{path}">\n{state[: mem.STATE_CAP]}\n</state>')
    return "\n\n".join(parts)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    try:
        text = build(
            data.get("cwd") or os.getcwd(), bool(os.environ.get("SAKURA_COORDINATOR"))
        )
    except Exception:
        return  # memory must never stop a session from starting
    if text:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": text,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
