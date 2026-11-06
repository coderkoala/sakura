#!/usr/bin/env python3
"""UserPromptSubmit hook — do the lookups BEFORE the model answers.

A 9b with stale training can't be trusted to decide when to look something up, pick the right
source, or even retype a URL correctly. So the harness does it: this hook runs on every prompt and
injects authoritative context the model then relays.

  1. The prompt is classified by the model that's already loaded (hooks/intent.py: one schema-
     constrained JSON call, no model swap), separating what the user means from what the words say.
  2. Generic lookups answer by intent (mcp/sakura-web/lookups.py): office-holders from Wikipedia's
     office infobox cross-checked with Wikidata, a tool's version from its registry, the project's
     pins from its manifests. Guards keep lookups out when they'd mislead: past or fictional
     questions, "don't look it up", another machine. No lookup beats a wrong one.
  3. A page is fetched only when the user asked to read it and it's public and read-only, so the
     model doesn't retype (and misspell) the URL. No approval gate covers that request.
If the router fails, the older heuristics run instead. Never blocks the prompt.

Contract: UserPromptSubmit JSON on stdin; prints
  {"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"..."}} or {}.
"""
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.parse

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "mcp", "sakura-web"))
sys.path.insert(0, HERE)
try:
    import webkit
    import lookups
except Exception:
    print("{}")
    sys.exit(0)
try:
    import intent as intent_router
except Exception:
    intent_router = None

URL = re.compile(r"https?://[^\s'\"<>)\]]+")
FEED_HINT = re.compile(r"advertises a feed: (\S+) ")

# Legacy heuristics (fallback only, when the router is unavailable).
TEMPORAL = re.compile(
    r"\b(current|currently|latest|newest|recent|recently|now|today|this year|this week|as of|up ?to ?date|"
    r"202[4-9]|20[3-9]\d|who('?s| is| are)|prime minister|president|ceo|chancellor|mayor|governor|price|cost|"
    r"how much|worth|stock|exchange rate|release(d|s)?|version|update|standings|score|results|winner|weather|"
    r"forecast|news|happening|election|champion|record)\b", re.I)
CODEY = re.compile(r"(/[\w.-]+/|~/|\.py\b|\.rs\b|\.js\b|\.sh\b|\bgit\b|\bsudo\b|\bnpm\b|\bcargo\b|"
                   r"\bfunction\b|\bcompile\b|\brefactor\b|\bstack ?trace\b|```)", re.I)

RELAY = ("Relay ONLY what this source says, citing it. Add nothing from memory — no extra names, dates, "
         "history or successors; your training is out of date and such details will be wrong.")


USE_AS_INPUT = "Use this as input for the task and go on to do it; don't stop at reporting it."
MUTATING_PATH = re.compile(r"(delete|remove|logout|signout|unsubscribe|confirm|approve|reset|activate)", re.I)
SECRET_QUERY = re.compile(r"(token|secret|password|passwd|api_?key|apikey|auth|signature|sig)=", re.I)


def _strip_quoted(prompt):
    """URLs inside quotes, code or pasted 'SYSTEM:' text are data, not something the user asked to open."""
    t = re.sub(r"```.*?```", " ", prompt, flags=re.S)
    t = re.sub(r"<<<.*?>>>", " ", t, flags=re.S)
    t = re.sub(r"\"[^\"\n]*\"|`[^`\n]*`", " ", t)
    return "\n".join(line for line in t.splitlines() if not re.match(r"\s*(system|assistant|user)\s*:", line, re.I))


def _safe_to_fetch(url):
    """No approval gate covers this GET, so only public, read-only-looking URLs."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        if host in ("localhost",) or host.endswith((".local", ".internal", ".lan")):
            return False
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                return False
    except Exception:
        return False
    return not (MUTATING_PATH.search(parts.path) or SECRET_QUERY.search(parts.query) or parts.username)


def prefetch(prompt):
    blocks = []
    for url in list(dict.fromkeys(URL.findall(_strip_quoted(prompt))))[:2]:
        url = url.rstrip(".,;:")
        if not _safe_to_fetch(url):
            continue
        try:
            page = webkit.fetch_url(url, 6000, deep=False)
        except Exception:
            continue  # the model reports a failed fetch itself; don't pretend it was fetched
        blocks.append(page)
        feed = FEED_HINT.search(page)
        if feed and _safe_to_fetch(feed.group(1)):
            try:
                blocks.append(webkit.fetch_url(feed.group(1), 5000, deep=False))
            except Exception:
                pass
    if not blocks:
        return None
    return ("The page(s) in the request, already fetched — work from this text; don't re-fetch or retype the URL.\n\n"
            + "\n\n---\n\n".join(blocks))


def _closing(it, fact):
    """What the model should do with a lookup: relay it, unless the user also wants work done."""
    if it.get("action_requested"):
        return fact + "\n" + USE_AS_INPUT
    if "Sources disagree" in fact or "may be out of date" in fact:
        return fact  # it carries its own instruction; "relay only" would hide the uncertainty
    return fact + "\n" + RELAY


def _title_matches(wiki, query):
    """Only relay a Wikipedia summary that's actually about the thing asked (not a same-named film)."""
    m = re.match(r"Wikipedia: (.+)", wiki or "")
    if not m:
        return False
    title = {w.lower() for w in re.findall(r"[^\W\d_]{3,}", m.group(1))}
    return bool(title & {w.lower() for w in re.findall(r"[^\W\d_]{3,}", query or "")})


def _live(source, query, limit=25):
    """A live lookup, on a clock: the hook has to finish, and a slow source can't hold up the answer."""
    import threading
    import live
    got = []

    def run():
        try:
            got.append(live.dispatch(source, query))
        except Exception as e:
            sys.stderr.write(f"[web_ground] live {source} failed: {e}\n")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(limit)
    return got[0] if got else None


def by_intent(it, prompt, cwd):
    """Each guard encodes a way the words and the intent differ. No lookup beats a wrong one."""
    kind = it.get("intent")
    tool, eco = it.get("tool"), it.get("ecosystem") or "unknown"
    if it.get("no_lookup") or it.get("time_scope") in ("hypothetical", "fiction"):
        return []
    out = []
    source = it.get("live_source")
    if source and source != "none" and it.get("time_scope") != "historical":
        found = _live(source, it.get("live_query"))
        if found:
            out.append(_closing(it, found))
            if kind != "tool_version":
                return out
    if kind == "current_fact" and it.get("time_scope") == "historical":
        past = lookups.historical(it.get("query") or prompt, prompt)
        return [past + "\nAnswer from these rows, citing the source. Nothing else in this machine's files is relevant."] if past else []
    if kind == "read_url":
        page = prefetch(prompt)
        if page:
            out.append(page)
    elif kind == "current_fact" and it.get("time_scope") == "current":
        holder = lookups.officeholder(it.get("subject"), it.get("role")) if it.get("role") else None
        if holder:
            out.append(_closing(it, holder))
        else:
            query = it.get("query") or prompt
            wiki = webkit.wikipedia(query)
            if _title_matches(wiki, query):
                out.append(_closing(it, wiki))
    elif kind in ("tool_version", "project_version", "docs_howto", "code_task", "system_task"):
        target = it.get("version_target")
        if target == "remote_host":
            return []  # the local machine and the registry say nothing about another host
        if kind == "tool_version" and target == "registry" and it.get("time_scope") == "current":
            latest = lookups.tool_latest(tool, eco, explicit=_named_registry(prompt, eco))
            if latest:
                out.append(_closing(it, latest + " Don't curl a docs site."))
        if kind != "system_task" or target == "this_machine":
            pinned = webkit.version_context(prompt, cwd, extra_tools=[tool] if tool else None)
            if pinned:
                out.append(pinned)
    return out


def _named_registry(prompt, eco):
    """Did the user say which registry, as in "the npm package tokio"?"""
    words = {"npm": "npm|node", "pypi": "pypi|pip|python", "crates": "crates?|cargo|rust", "composer": "composer|packagist|php"}
    return bool(re.search(rf"\b(?:{words.get(eco, eco)})\b", prompt, re.I))


def legacy(prompt, cwd):
    for fn, wrap in ((webkit.country_leader, RELAY), (webkit.latest_version, RELAY)):
        try:
            hit = fn(prompt)
        except Exception:
            hit = None
        if hit:
            return [hit + "\n" + wrap]
    try:
        pinned = webkit.version_context(prompt, cwd)
    except Exception:
        pinned = None
    if pinned:
        return [pinned]
    if CODEY.search(prompt) or not TEMPORAL.search(prompt):
        return []
    try:
        return ["Live lookup (Wikipedia-first) for this question; answer from it and cite it:\n\n"
                + webkit.web_search(prompt, 5)]
    except Exception:
        return []


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("{}")
        return
    prompt = (data.get("prompt") or "").strip()
    cwd = data.get("cwd") or "."
    if not prompt:
        print("{}")
        return
    contexts = []
    # The router sees every prompt: long ones are excerpted head + tail. If it fails we fall back to the
    # old heuristics, which never fetch a URL: no unapproved request without a classified read intent.
    it = intent_router.classify(prompt, data.get("model")) if intent_router else None
    try:
        contexts = by_intent(it, prompt, cwd) if it else legacy(prompt, cwd)
    except Exception as e:
        sys.stderr.write(f"[web_ground] lookup failed: {e}\n")
    if not contexts:
        print("{}")
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        # <lookup> marks this as turn-scoped evidence, so the harness can place it beside the question.
        "additionalContext": ("<lookup>\nAlready looked up for you this turn. Use this; do NOT run these lookups again.\n\n"
                              + "\n\n=====\n\n".join(contexts)[:14000] + "\n</lookup>"),
    }}))


if __name__ == "__main__":
    main()
