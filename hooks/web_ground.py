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
    cwd = data.get("cwd") or "."
    if not prompt or len(prompt) > 400:
        print("{}")
        return

    def inject(context):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit", "additionalContext": context}}))

    # 1. "Who is the current <PM/president/...> of <place>" — authoritative Wikidata (not bot-blocked).
    try:
        leader = webkit.country_leader(prompt)
    except Exception:
        leader = None
    if leader:
        inject("This asks for a current office-holder. An authoritative Wikidata lookup was run for "
               "you; answer from it directly and cite the source. Do not contradict it from memory.\n\n" + leader)
        return

    # 2a. "What is the latest/current version of <tool>" — answer from the authoritative package
    # registry (Packagist/npm/PyPI/crates/GitHub), which is keyless and not CAPTCHA-blocked. This is
    # the fix for the model curling laravel.com and hallucinating "Laravel 11".
    try:
        latest = webkit.latest_version(prompt)
    except Exception:
        latest = None
    if latest:
        inject("This asks for a tool's current version. An authoritative registry lookup was run for you — "
               "answer from it and cite the source; do NOT curl a docs site or answer from memory.\n\n" + latest)
        return

    # 2b. Version grounding — runs for tech/coding prompts too (the CODEY gate below would skip them).
    # The model's training is stale; answering about a tool's old version when the project is on a new
    # one is harmful. Inject the real versions from the project's manifests and the installed CLIs.
    try:
        versions = webkit.version_context(prompt, cwd)
    except Exception:
        versions = None
    if versions:
        inject(versions)
        return

    # 3. Other time-sensitive questions: live search (Wikipedia-first; engines are often blocked).
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
        "memory. If they don't cover it, say so. Web search engines may be blocking this host — if the "
        "results say so, do NOT retry with curl/grep on a search engine; use `wikipedia` or `fetch_url` "
        "on a specific URL instead.\n\n" + results
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
