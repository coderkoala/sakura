#!/usr/bin/env python3
"""Stop hook — reject answers that assert facts the turn never retrieved.

One general check instead of a prompt rule per failure. Before the final answer is shown, the
claims a reader could verify — version numbers, years/dates, and (on fact-lookup turns) proper
names — are compared against the evidence gathered THIS turn: the user's prompt, the context the
grounding hook injected, and every tool output. A claim found nowhere in that evidence is coming
from stale training. The hook blocks once, listing those claims, and the model must either verify
them with a tool or drop them. `stop_hook_active` limits it to one retry per turn.

Turn shapes:
  grounded (evidence beyond the prompt) — versions, years and proper names must be supported.
  ungrounded (no tools ran, nothing injected) — if the answer asserts something CURRENT (a
    version/year next to "current/latest/now/as of…"), block and send it to look it up first.
  everything else passes untouched (plain chat, explanations, code that cites nothing volatile).

Contract: Stop JSON on stdin (transcript_path, last_assistant_message, stop_hook_active);
prints {"decision":"block","reason":…} or nothing. Self-test: python3 claim_check.py --selftest
"""
import json
import re
import sys

VERSION = re.compile(r"(?<![\w.])v?(\d+\.\d+(?:\.\d+){0,2})(?![\w.]*\d)")
YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
CURRENT = re.compile(r"\b(current(ly)?|latest|newest|now|today|as of|at present|right now|recent(ly)?|this year|lts|stable)\b", re.I)
# Runs of capitalised words: candidate proper names (sentence-initial words are dropped in code).
NAME = re.compile(r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*")
CALENDAR = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
            "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"}
COMMON_CAPS = {
    "I", "The", "This", "That", "These", "Note", "However", "Based", "According", "Source", "Sources",
    "Wikipedia", "Wikidata", "Packagist", "PyPI", "GitHub", "Markdown", "JSON", "API", "URL", "HTML",
    "Linux", "Ubuntu", "Python", "Bash", "Shell", "Prime", "Minister", "President", "King", "Queen",
    "Government", "Republic", "Federal", "Democratic", "Office", "Head", "State", "LTS", "Long", "Term", "Support",
}
FACT_TURN = re.compile(r"(Wikidata|registry, fetched|registries \(they|Wikipedia:|Live lookup)", re.I)


def norm(s):
    return re.sub(r"\s+", " ", s.lower())


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(text_of(c) for c in content)
    if isinstance(content, dict):
        return " ".join(text_of(v) for k, v in content.items() if k in ("text", "output", "content", "stdout", "result"))
    return ""


def turn_evidence(transcript_path):
    """(prompt, evidence_text, grounded, fact_turn) for the last turn in a rollout JSONL."""
    items = []
    try:
        for line in open(transcript_path, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") == "response_item":
                items.append(d.get("payload", {}))
    except Exception:
        return "", "", False, False
    # last real user prompt (skip the AGENTS.md / environment preamble messages)
    start = 0
    prompt = ""
    for i, p in enumerate(items):
        if p.get("type") == "message" and p.get("role") == "user":
            t = text_of(p.get("content"))
            if not t.lstrip().startswith(("# AGENTS.md", "<environment_context", "<user_instructions")):
                start, prompt = i, t
    evidence, grounded, fact = [], False, False
    for p in items[start + 1:]:
        typ = p.get("type")
        if typ == "message" and p.get("role") == "developer":
            t = text_of(p.get("content"))
            evidence.append(t)
            grounded = True
            fact = fact or bool(FACT_TURN.search(t))
        elif typ in ("function_call_output", "custom_tool_call_output", "mcp_tool_call_output"):
            evidence.append(text_of(p.get("output")))
            grounded = True
        elif typ in ("function_call", "custom_tool_call"):
            evidence.append(text_of(p.get("arguments")) + " " + str(p.get("input", "")))
    return prompt, "\n".join(evidence), grounded, fact


def unsupported_claims(answer, prompt, evidence, check_names):
    hay = norm(prompt + "\n" + evidence)
    hay_digits = re.sub(r"[^\d.]", " ", hay)
    out = []
    for m in VERSION.finditer(answer):
        v = m.group(1)
        if v not in hay_digits and v.rstrip(".0") not in hay_digits:
            out.append(v)
    for m in YEAR.finditer(answer):
        if m.group(1) not in hay:
            out.append(m.group(1))
    if check_names:
        for m in NAME.finditer(answer):
            words = m.group(0).split()
            before = re.sub(r"[*_`#>\s]+$", "", answer[:m.start()])
            if not before or before[-1] in ".!?:\n-•|" or before.endswith(("1.", "2.", "3.")):
                words = words[1:]  # sentence/bullet start: first word is capitalised anyway
            words = [w for w in words if w not in COMMON_CAPS and w not in CALENDAR and len(w) >= 2]
            if words and not any(norm(w) in hay for w in words):
                out.append(" ".join(words))
    seen, uniq = set(), []
    for c in out:
        if c.lower() not in seen:
            seen.add(c.lower())
            uniq.append(c)
    return uniq


def decide(answer, prompt, evidence, grounded, fact):
    """Return a block reason or None."""
    if not answer or not answer.strip():
        return None
    if grounded:
        claims = unsupported_claims(answer, prompt, evidence, check_names=fact)
        if claims:
            listed = ", ".join(f"“{c}”" for c in claims[:8])
            return (f"Your answer states {listed}, which appear in none of the sources retrieved this turn "
                    f"(the injected lookup or your tool outputs). That detail is coming from stale training and "
                    f"is likely wrong. Either verify each one with a tool now, or rewrite the answer without "
                    f"them, keeping only what the sources say.")
        return None
    # Ungrounded: only object when it asserts something current without having looked.
    for sent in re.split(r"(?<=[.!?\n])\s+", answer):
        if CURRENT.search(sent) and (VERSION.search(sent) or YEAR.search(sent)):
            return ("You stated a current fact (a version or date) without looking it up this turn, and your "
                    "training is stale. Look it up first — for a tool's version: `fetch_url` its registry/docs "
                    "or check the project's manifest; for facts: `wikipedia \"<topic>\"` / `web_search` — then "
                    "answer only from what that returns, citing it.")
    return None


# A final message that only announces the next step ("Let me check X:", "I'll fix that.") — the small
# models end turns this way instead of making the tool call.
ANNOUNCE = re.compile(
    r"^(?:ok(?:ay)?[,.!]?\s*|now[,]?\s*|next[,]?\s*|first[,]?\s*|sure[,.!]?\s*|alright[,.!]?\s*)*"
    r"(?:(?:i'?ll|i will|i'?m going to|i am going to|let me|let's|let us|going to)\b|step \d+[:.)])",
    re.I,
)
MAX_CONTINUES = 3  # per turn: never trap the model in a loop


def continuation_reason(answer):
    """Block an empty final message or one that only announces work it never did."""
    a = (answer or "").strip()
    if not a:
        return ("You ended the turn without writing an answer. Write the answer now, from the tool output above "
                "(or, if something is still missing, run the tool call that gets it, then answer).")
    last = re.split(r"(?<=[.!?])\s+|\n+", a)[-1].strip(" *_`#>-")
    if len(a) < 400 and (a.endswith(":") or ANNOUNCE.search(last) or ANNOUNCE.search(a)):
        return (f"You ended the turn announcing a step instead of doing it (“{a[:120]}”). Do it now — make the "
                "tool call, check its output — and end with the actual result, not a plan.")
    return None


def _bump(turn_id):
    """Count continuations for this turn; returns the new count."""
    import os
    d = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "sakura-hooks")
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"stop-{re.sub(r'[^A-Za-z0-9_-]', '', turn_id or 'x')}")
        n = int(open(p).read() or 0) + 1 if os.path.exists(p) else 1
        open(p, "w").write(str(n))
        return n
    except Exception:
        return MAX_CONTINUES + 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    answer = data.get("last_assistant_message") or ""
    # 1. Continuation: empty or announce-only endings get sent back, at most MAX_CONTINUES per turn.
    cont = continuation_reason(answer)
    if cont:
        if _bump(data.get("turn_id")) <= MAX_CONTINUES:
            print(json.dumps({"decision": "block", "reason": cont}))
        return
    # 2. Claims: checked once per turn (stop_hook_active means we already sent it back once).
    if data.get("stop_hook_active"):
        return
    path = data.get("transcript_path")
    prompt, evidence, grounded, fact = turn_evidence(path) if path else ("", "", False, False)
    reason = decide(answer, prompt, evidence, grounded, fact)
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))


def selftest():
    ev_pm = ("A current office-holder was looked up for you (authoritative Wikidata). The current head of "
             "government of Nepal is Pushpa Kamal Dahal (in office since 2022-12-26).")
    ev_ver = "A tool's current version was looked up (authoritative registry). The latest published version of laravel is v13.39.0"
    cases = [
        # (answer, prompt, evidence, grounded, fact, expect_block)
        ("The current Prime Minister of Nepal is **Pushpa Kamal Dahal**, in office since December 26, 2022.",
         "who is the pm of nepal", ev_pm, True, True, False),
        ("The Prime Minister of Nepal is **Pracharjo Chhepa** (also known as Pushpa Kamal Dahal). In November 2025 he won.",
         "who is the pm of nepal", ev_pm, True, True, True),
        ("The current Prime Minister of Nepal is Pushpa Kamal Dahal (popularly known as PT Panubari), since 2022.",
         "who is the pm of nepal", ev_pm, True, True, True),
        ("The latest Laravel is v13.39.0, per Packagist.", "laravel lts", ev_ver, True, True, False),
        ("Current LTS is Laravel 12.5.x while 13.39.0 is latest.", "laravel lts", ev_ver, True, True, True),
        ("Laravel 11 is the current LTS (released 2023).", "laravel lts", "", False, False, True),
        ("Hi!", "say hi", "", False, False, False),
        ("A monad is a design pattern for chaining computations.", "explain monads", "", False, False, False),
        ("Fixed: add() now returns a + b. `python3 -c ...` printed 5.", "fix calc.py",
         "def add(a, b):\n    return a + b\n5\n", True, False, False),
        ("Python 3.12.3 is installed; wrote it to version.txt.", "chain", "Python 3.12.3\n", True, False, False),
    ]
    bad = 0
    conts = [("", True), ("Let me check if ruff is installed:", True), ("I'll check the project structure and configuration files.", True),
             ("The output has a leading space. Let me fix that:", True), ("Step 3: Creating the tar.gz archive.", True),
             ("The latest Laravel is v13.39.0, per Packagist.", False), ("Fixed: add() now returns a + b; it printed 5.", False),
             ("hi", False)]
    for ans, want in conts:
        if (continuation_reason(ans) is not None) != want:
            bad += 1
            print(f"continuation {'SHOULD BLOCK' if want else 'SHOULD PASS'}: {ans!r}")
    cases_total = len(conts)
    for ans, pr, ev, g, f, want in cases:
        got = decide(ans, pr, ev, g, f) is not None
        if got != want:
            bad += 1
            print(f"{'SHOULD BLOCK' if want else 'SHOULD PASS'}: {ans[:70]}")
            if got:
                print("   reason:", decide(ans, pr, ev, g, f)[:120])
    total = len(cases) + cases_total
    print(f"claim_check selftest: {total - bad}/{total} ok")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
