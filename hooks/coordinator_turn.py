#!/usr/bin/env python3
"""UserPromptSubmit, coordinator sessions only: put the one rule that matters right beside the request."""
import json
import os

if os.environ.get("SAKURA_COORDINATOR"):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
        "<lookup>\nYou're the coordinator. Don't edit anything or write code yourself. To change something, your command is "
        "`sakura-worker <<'JOB'` with `verify:` and `scope:` lines, a blank line, the brief and `JOB`, one job per step."
        "\n</lookup>")}}))
