#!/usr/bin/env python3
"""UserPromptSubmit hook — ground the model in live web data for time-sensitive questions.

The local generalist is weak and will confidently answer current-fact questions from stale training.
This hook runs on every prompt; when the prompt looks like it asks about something that changes over
time, it runs a web search and injects the results as additional context, so the model answers from
real data with source URLs instead of guessing. Stdlib only; shares webkit with the MCP server/CLIs.

Contract: JSON on stdin (UserPromptSubmit), JSON on stdout with
  {"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"..."}}
Emitting nothing (or {}) injects no context. Never blocks the prompt.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "mcp", "sakura-web"))
try:
    import webkit
except Exception:
    print("{}")
    sys.exit(0)

# Markers that a question is about something that changes over time.
TEMPORAL = re.compile(
    r"\b(current|currently|latest|newest|recent|recently|now|today|this year|this week|"
    r"as of|up ?to ?date|up-to-date|202[4-9]|20[3-9]\d|"
    r"who('?s| is| are)|prime minister|president|ceo|chancellor|mayor|governor|"
    r"price|cost|how much|worth|stock|exchange rate|"
    r"release(d|s)?|version|update|standings|score|results|winner|weather|forecast|"
    r"news|happening|election|champion|record)\b",
    re.I,
)
# Don't ground shell/coding/file work — the agent should just act there.
CODEY = re.compile(
    r"(/[\w.-]+/|~/|\.py\b|\.rs\b|\.js\b|\.sh\b|\bgit\b|\bsudo\b|\bnpm\b|\bcargo\b|"
    r"\bfunction\b|\bcompile\b|\brefactor\b|\bstack ?trace\b|```)",
    re.I,
)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("{}")
        return
    prompt = (data.get("prompt") or "").strip()
    if not prompt or len(prompt) > 400:
        print("{}")
        return
    if CODEY.search(prompt) or not TEMPORAL.search(prompt):
        print("{}")
        return
    try:
        results = webkit.web_search(prompt, 5)
    except Exception as e:
        print("{}")
        sys.stderr.write(f"[web_ground] search failed: {e}\n")
        return
    context = (
        "Live web search was run for this question because it may concern current facts your training "
        "is too old to know. Answer from these results and cite the URL(s); do not contradict them with "
        "memory. If they don't cover it, say so or search again with a better query.\n\n" + results
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
