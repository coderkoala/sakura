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
import os
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
            # Hook prompts are recorded as user messages; the turn's prompt is what the user actually wrote.
            if not t.lstrip().startswith(("# AGENTS.md", "<environment_context", "<user_instructions", "<hook_prompt", "<lookup>")):
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


def used_tools(transcript_path):
    """Did this turn make any tool call? (True when unknown, so a read failure never blocks an answer.)"""
    try:
        items = [json.loads(l) for l in open(transcript_path, encoding="utf-8")]
    except Exception:
        return True
    items = [d.get("payload", {}) for d in items if d.get("type") == "response_item"]
    last_user = max((i for i, p in enumerate(items) if p.get("type") == "message" and p.get("role") == "user"), default=-1)
    # Hook prompts are user messages too, so look back through the whole turn from the real prompt.
    for i in range(last_user, -1, -1):
        p = items[i]
        if p.get("type") == "message" and p.get("role") == "user" and "hook_prompt" not in text_of(p.get("content"))[:20]:
            last_user = i
            break
    return any(p.get("type") in ("function_call", "custom_tool_call") for p in items[last_user + 1:])


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
MAX_CONTINUES = 3  # in a row: never trap the model in a loop
MAX_TOTAL_CONTINUES = 12


# A progress note, not an ending: "Now creating the archive.", "Step 2 done.", "**2. Write the version:**"
PROGRESS = re.compile(r"(?:\bnow\s+\w+ing\b|\bnext\b[,:]?\s|\bstep\s+\d+\b|^\w+ing\s+(?:it|that|this)\b)", re.I)


# A command for the user to run, when the request was for the work itself.
WRITES_IN_FENCE = re.compile(r"```[a-z]*\n(?:(?!```).)*?(?:(?:^|\s)>>?\s*[\w/~$.]|\btee\s|\bsudo\s|\bchmod\s|\bcp\s|\bmv\s|\bedit_file\s|\bsakura-tool\s+keep\b)", re.S)
ASKING_HOW = re.compile(r"^\W*(how\b|what\b|why\b|which\b|explain\b|show me\b|can you (?:explain|show)\b|write me a (?:command|one-?liner)\b|give me a (?:command|one-?liner)\b)|\?\s*$", re.I)


# Nothing but code, as an answer to a request to get something done: the tool call came out as text.
ONLY_CODE = re.compile(r"^\s*(?:```[^\n]*\n.*\n```|`[^`\n]+`)\s*$", re.S)
WANTS_ACTION = re.compile(r"\b[\w-]+\.[a-z]{1,5}\b|\b(?:run it|then run|remember|save|create|install|delete|deploy|commit|restart)\b", re.I)


def wrote_out_the_call(answer, prompt):
    return bool(ONLY_CODE.match(answer or "")) and bool(WANTS_ACTION.search(prompt or "")) and not ASKING_HOW.search((prompt or "").strip())


def handed_over(answer, prompt):
    """The answer gives the user a command that changes something, and they asked for the thing, not for how to do it."""
    return bool(WRITES_IN_FENCE.search(answer or "")) and not ASKING_HOW.search((prompt or "").strip())


# The user wants this to last, the turn wrote a script, and nothing went through the gate.
LASTING = re.compile(r"\b(future sessions?|next time|from now on|keep (?:it|this|that)|keep needing|permanent(?:ly)?|for later|stick around|still be (?:there|here)|there (?:later|next))\b", re.I)
WROTE_SCRIPT = re.compile(r"#!|chmod\s+\S*\+?x")
KEPT = re.compile(r"\bkept: \S+, at ")


def tool_not_kept(prompt, evidence):
    return bool(LASTING.search(prompt or "") and WROTE_SCRIPT.search(evidence or "") and not KEPT.search(evidence or ""))


# A sum done in the head. Local models get them wrong and sound just as sure. This has to ask for an actual sum: "what does
# 204 mean" once sent the model hunting for numbers, all the way to a URL it had been told not to open.
ARITHMETIC = re.compile(r"\b(?:the\s+(?:grand\s+)?total|their\s+total|in\s+total|sum\s+of|add(?:ed)?\s+(?:them\s+)?up|average\s+of|mean\s+of|how\s+many\s+in\s+all|altogether)\b", re.I)
COMPUTED = re.compile(r"\bpython3?\b|\bbc\b|\bawk\b|\$\(\(|\bexpr\b|\bwc\b|\bnumfmt\b")


def arithmetic_reason(answer, prompt, evidence, ran_tools=True):
    if not ran_tools or not ARITHMETIC.search(prompt or "") or not re.search(r"\d", answer or "") or COMPUTED.search(evidence or ""):
        return None
    return ("The user asked for a sum, and you didn't compute it with a command. Add the numbers you already have using `python3 -c`, then give your "
            "whole answer again with that result in it, everything else unchanged. Don't look anything else up. If no sum was actually asked for, "
            "repeat your answer exactly as it was.")


def bare_done(answer, prompt, results):
    """A one-word ending on a numbered job, with fewer commands run than steps asked for."""
    total = steps_in(prompt)
    return bool(total and results is not None and len((answer or "").strip()) <= 40 and len(results) < total)


def steps_in(prompt):
    """How many steps the user numbered: "1) do x, 2) do y" -> 2. Zero if they didn't number them."""
    nums = [int(n) for n in re.findall(r"(?:^|[\s,;:(])(\d{1,2})[).]\s", prompt or "")]
    return max(nums) if len(nums) >= 2 and sorted(nums) == list(range(1, max(nums) + 1)) else 0


def stopped_at_step(answer, total):
    """The last step this message reports, when it stops before the user's last step, else None."""
    if not total:
        return None
    seen = [int(n) for n in re.findall(r"(?:\bstep\s+|(?:^|\n)[\s*_#]*)(\d{1,2})\b[).:\s]", answer, re.I)]
    return max(seen) if seen and max(seen) < total else None


def continuation_reason(answer, prompt=""):
    """Block an empty final message, one that only announces work, or one that stops partway through."""
    a = (answer or "").strip()
    if not a:
        return ("You ended the turn without writing an answer. Write the answer now, from the tool output above "
                "(or, if something is still missing, run the tool call that gets it, then answer).")
    last = re.split(r"(?<=[.!?])\s+|\n+", a)[-1].strip(" *_`#>-")
    if len(a) < 400 and (a.endswith(":") or ANNOUNCE.search(last) or ANNOUNCE.search(a)):
        return (f"You ended the turn announcing a step instead of doing it (“{a[:120]}”). Do it now — make the "
                "tool call, check its output — and end with the actual result, not a plan.")
    total = steps_in(prompt)
    at = stopped_at_step(a, total)
    if at:
        return (f"You stopped at step {at} of the {total} the user asked for. Carry on with step {at + 1} now, make the "
                "tool calls for every remaining step, and only then give the final result.")
    if total and len(a) < 400 and PROGRESS.search(last):
        return ("That's a progress note, and the user asked for several steps. Finish every remaining step with tool "
                "calls, then give the final result.")
    return None


# First-person or passive claims that work got done. Tight on purpose: "working on" or "the fix is" don't count.
DONE_CLAIM = re.compile(
    r"^\W*(done|fixed|deployed|finished|all set)\b"
    r"|\bI(?:'ve| have)?\s+(?:\w+ly\s+)?(fixed|created|updated|deployed|installed|pushed|committed|restarted|removed|"
    r"deleted|added|wrote|ran|tested|verified|configured|changed|moved)\b"
    r"|\b(?:has|have|is|are|was|were) (?:now )?(?:been )?(?:successfully )(?:\w+)\b"
    r"|\b(?:has|have) been (fixed|created|updated|deployed|installed|pushed|committed|restarted|removed|deleted|added)\b"
    r"|\bsuccessfully\b",
    re.I | re.M)
FAIL_ADMITTED = re.compile(
    r"\b(fail(ed|s|ure|ing)?|error(ed|s)?|couldn'?t|could not|cannot|can'?t|unable|denied|not found|didn'?t|doesn'?t|"
    r"blocked|refused|exit(ed)?( with)?( code| status)? ?[1-9]|non-?zero|expected)\b", re.I)
EXIT_CODE = re.compile(r"(?:Process exited with code|Exit code:?) (-?\d+)")


def turn_results(transcript_path):
    """Exit codes of this turn's tool calls, in order (None where the output doesn't say)."""
    try:
        items = [json.loads(l) for l in open(transcript_path, encoding="utf-8")]
    except Exception:
        return None
    items = [d.get("payload", {}) for d in items if d.get("type") == "response_item"]
    start = 0
    for i, p in enumerate(items):
        if p.get("type") == "message" and p.get("role") == "user" and "hook_prompt" not in text_of(p.get("content"))[:200] \
                and not text_of(p.get("content")).lstrip().startswith(("# AGENTS.md", "<environment_context", "<user_instructions")):
            start = i
    out = []
    for p in items[start + 1:]:
        if p.get("type") in ("function_call_output", "custom_tool_call_output", "mcp_tool_call_output"):
            m = EXIT_CODE.search(text_of(p.get("output"))[:300])
            out.append(int(m.group(1)) if m else None)
    return out


def completion_reason(answer, results, prompt=""):
    """Block a claim of finished work when no tool ran, or when the last command failed and the answer doesn't say so."""
    if results is None or not answer or not DONE_CLAIM.search(answer):
        return None
    if not results:
        if ASKING_HOW.search((prompt or "").strip()):
            return None  # they asked a question, and "the request completed successfully" can just be the answer
        return ("You said the work is done, but you ran no tool this turn, so nothing happened. Do it now with tool "
                "calls and report what the output shows. If the user only wanted an explanation, give that explanation again and nothing else.")
    if results[-1] not in (None, 0) and not FAIL_ADMITTED.search(answer):
        return (f"Your last command exited with code {results[-1]}, and your answer says the work succeeded. Read that "
                "output: fix the cause and re-run it, or tell the user plainly that it failed.")
    return None


def _bump(turn_id, progress=0):
    """Count continuations for this turn; returns the new count. Progress restarts the count, up to MAX_TOTAL_CONTINUES in
    the whole turn. Callers only report progress on a job the user numbered: elsewhere, the limit is what stops a model that
    can't reach something from hunting further and further afield, and the last chance is what makes it say so."""
    d = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "sakura-hooks")
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"stop-{re.sub(r'[^A-Za-z0-9_-]', '', turn_id or 'x')}")
        n, total, seen = 0, 0, 0
        if os.path.exists(p):
            parts = (open(p).read().split() + ["0", "0", "0"])[:3]
            n, total, seen = int(parts[0]), int(parts[1]), int(parts[2])
        if progress > seen:
            n = 0
        n, total = n + 1, total + 1
        open(p, "w").write(f"{n} {total} {progress}")
        return n if total <= MAX_TOTAL_CONTINUES else MAX_CONTINUES + 1
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
    path = data.get("transcript_path")
    prompt, evidence, grounded, fact = turn_evidence(path) if path else ("", "", False, False)
    # 1. Continuation: empty, announce-only or partway endings get sent back, at most MAX_CONTINUES per turn.
    cont = continuation_reason(answer, prompt)
    if not cont and steps_in(prompt) and not used_tools(path):
        cont = ("You listed the steps without doing them. If they are work to carry out, do them now with tool calls, "
                "then give the result. If the user only asked for an explanation, restate your answer.")
    if not cont and tool_not_kept(prompt, evidence):
        cont = ("The user wants this command to last, and it hasn't been kept: a script on disk doesn't follow them. Remove anything you "
                "installed by hand, then run this with its real input and expected output:\n"
                "sakura-tool keep NAME ./FILE --about \"one line\" <<'CHECK'\nprintf 'input\\n' | NAME | grep -qx 'expected'\nCHECK\n"
                "Report what it prints. If it can't be kept, tell the user that.")
    if not cont and path and bare_done(answer, prompt, turn_results(path)):
        cont = ("The user numbered their steps, and you've run fewer commands than there are steps. Check each one with a command, do what's "
                "missing, and report what each one's output showed.")
    if not cont and wrote_out_the_call(answer, prompt) and not used_tools(path):
        cont = ("You wrote that out as text, so nothing happened. Do it now with an actual tool call, then report what the output shows. "
                "If the user only wanted to read the code, give it again and say that nothing was run.")
    if not cont and handed_over(answer, prompt) and not used_tools(path):
        cont = ("You wrote out commands and ran nothing, so nothing has happened. Run them yourself now with tool calls, then report "
                "what the output shows. If the user only wanted to read the commands, say that nothing was run.")
    if cont:
        n = _bump(data.get("turn_id"), len(turn_results(path) or []) if path and steps_in(prompt) else 0)
        if n == MAX_CONTINUES:  # the last chance: a turn must end with an answer, even if the answer is "I couldn't"
            cont = ("Stop trying new things now. Write your final answer from what you've seen: what worked, what didn't, "
                    "and what's blocking. If it couldn't be done, say that plainly. Make no more tool calls.")
        if n <= MAX_CONTINUES:
            print(json.dumps({"decision": "block", "reason": cont}))
        return
    # 2. Claims: checked once per turn (stop_hook_active means we already sent it back once).
    if data.get("stop_hook_active"):
        return
    reason = completion_reason(answer, turn_results(path) if path else None, prompt) or arithmetic_reason(answer, prompt, evidence, bool(turn_results(path) if path else None)) or decide(answer, prompt, evidence, grounded, fact)
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))


def _bump_selftest():
    import tempfile
    old = os.environ.get("XDG_CACHE_HOME")
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CACHE_HOME"] = d
        seen = [_bump("t", p) for p in (1, 1, 1, 2, 2)]  # three stalls, a tool run, one more stall
        stalled = [_bump("u", 0) for _ in range(5)]
        capped = [_bump("v", i) for i in range(1, 15)]
    if old is None:
        del os.environ["XDG_CACHE_HOME"]
    else:
        os.environ["XDG_CACHE_HOME"] = old
    return seen == [1, 2, 3, 1, 2] and stalled[3] > MAX_CONTINUES and capped[-1] > MAX_CONTINUES and capped[10] == 1


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
    chain = "do these in order: 1) make a dir, 2) write a file, 3) tar it, 4) list it"
    for ans, want in [("2) Version written.", True), ("Step 2 done — Python 3.14.4 written.", True),
                      ("Directory created.\n\n**2. Write python3 version output:**", True),
                      ("Step 2 done. Now writing that to version.txt.", True),
                      ("add() returns a - b instead of adding. Fixing it.", True),
                      ("All done. The archive contains build-test/version.txt.", False),
                      ("1. Created it\n2. Wrote it\n3. Tarred it\n4. Listed: build-test/version.txt", False)]:
        if (continuation_reason(ans, chain) is not None) != want:
            bad += 1
            print(f"chain {'SHOULD BLOCK' if want else 'SHOULD PASS'}: {ans!r}")
    if steps_in("fix calc.py in 2 hours") or steps_in("python 3.14 and node 26.") or steps_in("use v1. then 2.") > 2:
        bad += 1
        print("steps_in misread prose as steps")
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
    total = len(cases) + cases_total + 8
    for ans, results, want in (
        ("Done. The file is created.", [], True),
        ("I've fixed the bug.", [], True),
        ("Here is how you would fix it: change a to b.", [], False),
        ("The nginx service has been restarted.", [0, 1], True),
        ("I restarted nginx but it failed: port in use.", [0, 1], False),
        ("Fixed. The test passes.", [1, 0], False),
        ("Deployed v2.", [0], False),
        ("Deployed v2.", None, False),
        ("I fixed it.", [None], False),
    ):
        total += 1
        if bool(completion_reason(ans, results)) != want:
            bad += 1
            print(f"completion_reason wrong: {ans!r} {results} (wanted block={want})")
    fence = "```bash\ncat << 'EOF' > /usr/local/bin/x\n#!/bin/sh\nEOF\n```"
    make = "make me a command called x and keep it for future sessions"
    for got, want, label in (
        (handed_over(fence, make), True, "handed over a write"),
        (handed_over(fence, "how do I install x?"), False, "they asked how"),
        (handed_over("```bash\nls -la\n```", make), False, "a read isn't a handover"),
        (handed_over("all good", make), False, "no command"),
        (tool_not_kept(make, "cat > x <<E\n#!/bin/sh"), True, "script written, not kept"),
        (tool_not_kept(make, "#!/bin/sh\nkept: x, at /a/x"), False, "kept"),
        (tool_not_kept("fix the script", "#!/bin/sh"), False, "nobody asked for it to last"),
        (tool_not_kept(make, "ls"), False, "no script yet"),
        (wrote_out_the_call("```python\nprint(1)\n```", "write fizzbuzz.py that prints it, then run it"), True, "script written out"),
        (wrote_out_the_call('`sakura-memory add user "x"`', "remember that my host is bluefin"), True, "memory call written out"),
        (wrote_out_the_call("```python\nprint(1)\n```", "write a python function that adds two numbers"), False, "they asked for a snippet"),
        (wrote_out_the_call("```bash\nls\n```", "how do I save a file listing?"), False, "they asked how"),
        (wrote_out_the_call("Saved it. `x`", "remember x"), False, "more than code"),
        (bool(arithmetic_reason("Total: 7174", "give me the total", "cat a")), True, "a total from the head"),
        (bool(arithmetic_reason("Total: 7172", "give me the total", 'python3 -c "print(1+2)"')), False, "a computed total"),
        (bool(arithmetic_reason("It has 3 files", "list the files", "ls")), False, "no sum asked for"),
        (bool(arithmetic_reason("HTTP 204 means no content, 2xx is success", "what does HTTP status 204 mean?", "")), False, "'mean' isn't a sum"),
        (bool(arithmetic_reason("Total 7", "the total of a and b", "cat a", False)), False, "nothing was run to add up"),
        (handed_over("```\nedit_file --create f.py <<'EOF'\nprint(1)\nEOF\n```", "write fizzbuzz.py"), True, "edit_file left unrun"),
        (bare_done("Done.", "do: 1) a, 2) b, 3) c", [0]), True, "bare done"),
        (bare_done("Done.", "do: 1) a, 2) b", [0, 0]), False, "a command per step"),
        (bare_done("Done.", "fix it", [0]), False, "not numbered"),
        (_bump_selftest(), True, "progress restarts the continuation count"),
        (bool(completion_reason("204 means the request completed successfully.", [], "what does HTTP status 204 mean?")), False, "an explanation isn't a claim"),
        (bool(completion_reason("I fixed it.", [], "fix the bug")), True, "a claim with nothing run"),
    ):
        total += 1
        if got != want:
            bad += 1
            print(f"wrong: {label}")
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for role, text in (("user", "do: 1) a, 2) b"), ("assistant", "Step 1 done."), ("user", "<hook_prompt hook_run_id=\"x\">go on</hook_prompt>")):
            f.write(json.dumps({"type": "response_item", "payload": {"type": "message", "role": role,
                                                                     "content": [{"type": "input_text", "text": text}]}}) + "\n")
    if turn_evidence(f.name)[0] != "do: 1) a, 2) b":
        bad += 1
        print("turn_evidence took a hook prompt for the user's prompt")
    total += 1
    os.unlink(f.name)
    print(f"claim_check selftest: {total - bad}/{total} ok")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
