#!/usr/bin/env python3
"""PreToolUse guard — enforce the web rules instead of asking the model to follow them.

The 9b ignores "use fetch_url, not curl" in AGENTS.md. So this hook denies the failing patterns
outright and puts the exact replacement command in the denial reason, which the model then runs:

  - GUI openers (xdg-open, sensible-browser, firefox <url>, …): their output never reaches the agent.
  - curl/wget on a search engine: DuckDuckGo/Google/Bing/SearXNG CAPTCHA this host.
  - curl/wget of an HTML page (docs, Wikipedia, blogs): returns minified HTML/JS the model then
    fails to grep for minutes. fetch_url returns readable text and renders feeds.

Allowed: APIs and machine formats (JSON/XML/raw files), downloads (-o/-O), HEAD (-I), POST/data,
localhost, installers piped to sh, and anything piped to jq/python. Never blocks non-web commands.

Contract: PreToolUse JSON on stdin; prints a hookSpecificOutput deny, or nothing to allow.
Self-test: python3 tool_guard.py --selftest
"""
import json
import os
import re
import shlex
import sys

GUI_OPENERS = re.compile(r"(^|[\s;&|(])(xdg-open|sensible-browser|x-www-browser|gnome-open|kde-open5?|firefox|chromium|google-chrome|brave-browser)\b")
FETCHER = re.compile(r"(^|[\s;&|(])(curl|wget)\b")
URL = re.compile(r"https?://[^\s'\"|;&)<>]+")
SEARCH_ENGINE = re.compile(r"(duckduckgo\.com|google\.[a-z.]+/search|bing\.com/search|search\.brave\.com|searx|startpage\.com|yandex\.[a-z]+/search)", re.I)
MACHINE_URL = re.compile(
    r"(/api/|//api\.|\bapi\.|\.json\b|\.xml\b|\.rss\b|\.atom\b|\.txt\b|\.csv\b|\.ya?ml\b|\.toml\b|\.sh\b|\.py\b|"
    r"\.tar|\.tgz|\.gz\b|\.zip\b|\.deb\b|\.rpm\b|\.whl\b|\.iso\b|\.img\b|\.bin\b|\.exe\b|\.appimage\b|"
    r"raw\.githubusercontent|objects\.githubusercontent|registry\.|repo\.packagist|pypi\.org/pypi|"
    r"format=json|/feed\b|localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|/v\d+/|wikidata\.org/w/api\.php|/w/api\.php)",
    re.I,
)
DOWNLOAD_OR_API_FLAGS = re.compile(r"\s(-o|-O|--output|--remote-name|-I|--head|-X|--request|-d|--data[\w-]*|-F|--form|-T|--upload-file|--json)\b")
SAFE_PIPE = re.compile(r"\|\s*(jq|python3?\b|sh\b|bash\b|sudo\s+(ba)?sh|tar\b|gunzip|sha\d+sum|gpg)\b")


def verdict(command):
    """Return a denial reason for `command`, or None to allow."""
    if not command:
        return None
    m = GUI_OPENERS.search(command)
    if m:
        url = URL.search(command)
        target = f'fetch_url "{url.group(0)}"' if url else "fetch_url \"<url>\""
        return (f"Blocked: `{m.group(2)}` opens a GUI window — its output never reaches you, so you learn nothing. "
                f"To read the page, run: {target}")
    if not FETCHER.search(command):
        return None
    urls = URL.findall(command)
    if not urls:
        return None
    for url in urls:
        if SEARCH_ENGINE.search(url):
            return ("Blocked: search engines (DuckDuckGo, Google, Bing, SearXNG) serve this host a CAPTCHA, so "
                    "curl/wget on them returns nothing useful. Instead run: wikipedia \"<topic>\"  or  "
                    "web_search \"<query>\"  (Wikipedia-first; supplements with engines when they answer).")
    if DOWNLOAD_OR_API_FLAGS.search(" " + command) or SAFE_PIPE.search(command):
        return None
    page_urls = [u for u in urls if not MACHINE_URL.search(u)]
    if not page_urls:
        return None
    url = page_urls[0]
    alt = f'fetch_url "{url}"'
    wiki = re.search(r"wikipedia\.org/wiki/([^?#]+)", url)
    if wiki:
        title = wiki.group(1).replace("_", " ")
        alt = f'wikipedia "{title}"   (or: fetch_url "{url}" for the full article)'
    return (f"Blocked: curl/wget of a web page returns raw HTML/JavaScript that you cannot reliably parse with "
            f"grep/sed (that loop has cost minutes and still failed). Run this instead — it returns clean readable "
            f"text, follows redirects, and renders RSS/Atom feeds:  {alt}\n"
            f"curl is still fine for APIs/JSON, downloads (-o/-O), and HEAD (-I).")


# What a coordinator session may run. It reads, plans and briefs; a worker does everything else.
COORDINATOR_OK = {
    "sakura-worker", "sakura-memory", "sakura-recall", "consult", "wikipedia", "web_search", "fetch_url", "curated_search", "live", "view_file",
    "ls", "cat", "head", "tail", "wc", "rg", "grep", "find", "tree", "stat", "file", "pwd", "echo", "date", "which", "sort", "uniq", "cut", "true", "cd",
}
COORDINATOR_GIT = {"status", "log", "diff", "show", "branch", "rev-parse", "ls-files", "blame", "describe", "tag"}
WRITES = re.compile(r"(?<![0-9&])>(?!&)|\b(?:\d)>(?!&|/dev/null)|\s-delete\b|\s-exec\b|\s-execdir\b")


COORDINATOR_NO = """STOP. Don't retry that or try another tool: you're the coordinator, and only a worker can change things. Your next command must be:

sakura-worker <<'JOB'
verify: <a command that exits 0 only if it worked>
scope: <files it may change>

<what to do, in plain words>
JOB"""


# A script written straight into a directory on PATH skips the check that a kept tool has to pass, and doesn't follow the user
# to other machines. Binaries and a cp to a place the user named aren't affected.
PATH_DIR = r"(?:/usr/local/s?bin|/usr/s?bin|/opt/bin|(?:~|\$HOME|\$\{HOME\}|/home/[^/\s]+|/root)/(?:\.local/)?bin)/[\w.-]+"
SCRIPT_ON_PATH = re.compile(r"(?:>>?\s*[\"']?|\btee\s+(?:-a\s+)?[\"']?)" + PATH_DIR)


# Sending is outward-facing, and a worker's commands run with nobody to approve them.
MAIL_SEND = re.compile(r"\bhimalaya\b[^|;&\n]*\b(?:message\s+send|smtp\s+(?:send|raw)|(?:message\s+)?(?:compose|write|reply|forward|fwd)\b[^|;&\n]*--send)\b")
# Every other way out: another client, a mail server to install or start, SMTP by hand.
MAIL_OTHER = re.compile(r"(?:^|[\s;&|(]|/usr/s?bin/)(?:mail|mailx|mail\.mailutils|sendmail|msmtp|mutt|neomutt|swaks|ssmtp|postfix|postconf|exim4?)\b(?!\.)|\b(?:mailutils|postfix|exim4|msmtp|ssmtp|sendmail|swaks)\b[^|;&\n]*|smtplib|smtps?://|\b(?:EHLO|HELO|RCPT TO|MAIL FROM)\b|\b(?:nc|ncat|netcat|telnet|socat|s_client)\b[^|;&\n]*\b(?:25|465|587|2525|3025|3026)\b")
# himalaya reads the password from pass itself. Nothing else needs to see it.
READS_PASSWORD = re.compile(r"(?:^|[\s;&|(/])pass(?:\s+(?:show|ls|find|grep|git|otp|insert|edit|generate)\b|\s+email/)|\.password-store|passwd\.cmd")
PASSWORD_NO = ("Blocked: passwords stay in pass, out of this conversation. himalaya reads them by itself, so you never need to. If one seems wrong, tell the user to check it: "
               "pass insert email/NAME")
# They asked to see it first, so sending now would be taking that decision for them.
ASKED_FOR_DRAFT = re.compile(r"\bdraft\b|\bbefore (?:anything|it|you)\b|\b(?:show|let) me\b|\bdon'?t send\b|\bdo not send\b|\bnot send\b", re.I)
DRAFT_NO = "Blocked: the user asked to see this first. Show them the draft and end your turn. They'll tell you when to send it."
USE_HIMALAYA = ("Blocked: mail goes through himalaya here, and there's no mail server to set up. Run: "
                "himalaya message compose --to a@b.c --subject \"...\" --body \"...\" --send. If it isn't configured, tell the user to run sakura-mail-setup.")
WORKER_NO_MAIL = "You're a worker, so nobody can approve this. Don't send mail: leave a draft and report that it's waiting for the user."
# Standing orders that act on the user's behalf for weeks shouldn't come from something nobody is watching.
PA_STANDING = re.compile(r"(?:^|[\s;&|(/])pa\s+(?:autoreply\s+on|job\b|watch\b)|\bcrontab\b|\bsystemctl\s+--user\s+(?:enable|start)\b")
WORKER_NO_STANDING = "You're a worker, so nobody is here to approve a standing order. Report what you'd set up, and let the user turn it on."
GIT_PUSH = re.compile(r"\bgit\b[^|;&\n]*\bpush\b")
WORKER_NO_PUSH = "You're a worker, and your brief doesn't ask you to push. Leave it committed or uncommitted as the job says, and report it."
BIG_CAT = re.compile(r"^\s*cat\s+([^\s|;&<>]+)\s*$")
BIG_FILE = 20000


def big_cat_verdict(cmd, cwd):
    """A big file printed whole can fill the context in one step."""
    m = BIG_CAT.match(cmd)
    if not m:
        return None
    path = os.path.join(cwd or ".", os.path.expanduser(m.group(1)))
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= BIG_FILE:
        return None
    return (f"Blocked: {m.group(1)} is {size // 1024} KB, which would fill your context. Read it in pages: view_file {m.group(1)} [start] [end]. "
            f"To find something first: rg -n 'text' {m.group(1)}")


BREAK_SYSTEM = re.compile(r"--break-system-packages")
OVERWRITE = re.compile(r"(?:^|[\s;&|(])(?:cat\s*>|tee)\s*([^\s|;&<>'\"]+)\s*<<")
SUBSTANTIAL_LINES = 20


def packages_verdict(cmd):
    if not BREAK_SYSTEM.search(cmd):
        return None
    return ("Blocked: that changes the system's Python for one script. Use an isolated environment instead, which needs no install: "
            "uv run --with PACKAGE python3 script.py  (or: uv run --with PACKAGE python3 - <<'PY' ... PY)")


def overwrite_verdict(cmd, cwd):
    """A heredoc over a real file loses whatever the model didn't retype."""
    m = OVERWRITE.search(cmd)
    if not m:
        return None
    try:
        with open(os.path.join(cwd or ".", os.path.expanduser(m.group(1))), "rb") as f:
            lines = f.read().count(b"\n")
    except OSError:
        return None
    if lines <= SUBSTANTIAL_LINES:
        return None
    return (f"Blocked: {m.group(1)} already has {lines} lines, and this would replace all of them. Change only what needs changing:\n"
            f"edit_file {m.group(1)} <<'EDIT'\n@@old\nthe exact lines\n@@new\nwhat they become\n@@end\nEDIT\n"
            f"If replacing the whole file is really what the user asked for: edit_file --create --force {m.group(1)} <<'EOF'")


CONTAINER_START = re.compile(r"(?:^|[\s;&|(])(?:sudo(?:\s+-A)?\s+)?(?:docker|podman)\s+(?:run|create|compose\s+up|container\s+(?:run|create))\b")


def this_turn(transcript_path):
    """(what the user asked this turn, every command run this turn, whether an ssh in it failed to connect).
    ssh itself exits 255 for that."""
    prompt, commands, failed, calls = "", [], False, {}
    if not transcript_path:
        return prompt, commands, failed
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "response_item":
                    continue
                p = d.get("payload") or {}
                kind = p.get("type")
                if kind == "message" and p.get("role") == "user":
                    text = json.dumps(p.get("content"))
                    if "hook_prompt" not in text[:200] and "# AGENTS.md" not in text[:200] and "<environment_context" not in text[:200]:
                        prompt, commands, failed, calls = text, [], False, {}
                elif kind == "function_call":
                    calls[p.get("call_id")] = str(p.get("arguments"))
                    commands.append(str(p.get("arguments")))
                elif kind == "function_call_output" and re.search(r"\bssh\b", calls.get(p.get("call_id"), "")) \
                        and re.search(r"(?:exited with code|Exit code:?) 255\b", json.dumps(p.get("output"))[:400]):
                    failed = True
    except OSError:
        pass
    return prompt, commands, failed


def ssh_failed_this_turn(transcript_path):
    return this_turn(transcript_path)[2]


# Ways around a host that refused or didn't answer: another key, port, user or address, or changing the ssh config.
SSH_AROUND = re.compile(r"\b(?:ssh|scp|sftp)\b[^|;&\n]*?\s(-i\s*(\S+)|-p\s*(\d+)|-P\s*(\d+)|-l\s*(\S+)|-o\s*[\"']?(?:IdentityFile|Port|User|HostName|ProxyCommand|ProxyJump)\s*=?\s*([^\s\"']+))")
WRITES_CONFIG = re.compile(r"(?:\bsed\s+-i\S*|\bedit_file\b|\btee\b|>>?|\bcp\b|\bmv\b)[^|;&\n]*?(\S*(?:\.ssh/|ssh_config)\S*)")


def ssh_around_verdict(cmd, transcript_path):
    """Once a host has refused, trying other credentials or addresses is going where the user didn't send it."""
    if not transcript_path or not re.search(r"\b(?:ssh|scp|sftp|sed|edit_file|tee|cp|mv)\b|>", cmd):
        return None
    prompt, commands, failed = this_turn(transcript_path)
    if not failed:
        return None
    no = ("Blocked: ssh couldn't get in with what you were given, and that's your answer. Don't try another key, port, user or address, and don't change "
          "the ssh config. Report the error you saw and stop. If the user wants something else tried, they'll say so.")
    m = SSH_AROUND.search(cmd)
    if m and next((v for v in m.groups()[1:] if v), "") not in prompt:
        return no
    configs = set(re.findall(r"-F\s+(\S+?)(?:[\s\"'\\]|$)", " ".join(commands)))
    w = WRITES_CONFIG.search(cmd)
    if w or any(re.search(r"(?:\bsed\s+-i\S*|\bedit_file\b|\btee\b|>>?|\bcp\b|\bmv\b)[^|;&\n]*" + re.escape(c), cmd) for c in configs):
        return no
    return None


INSTALL_ON_PATH = re.compile(r"\b(?:mv|cp|install|ln)\b[^|;&\n]*\s" + PATH_DIR)


def keep_around_verdict(cmd, transcript_path):
    """A tool the gate refused, installed by hand anyway, is the check skipped."""
    if not transcript_path or not INSTALL_ON_PATH.search(cmd):
        return None
    prompt, commands, _ = this_turn(transcript_path)
    if not any("sakura-tool keep" in c for c in commands) or re.search(r"/(?:usr/local/s?bin|\.local/bin|bin)/", prompt):
        return None
    return ("Blocked: you're keeping this tool with sakura-tool, and copying it onto PATH by hand would skip the check. Read what keep told you, fix the check or the tool, "
            "and run keep again. If you can't get it to pass, say so.")


def stand_in_verdict(cmd, transcript_path):
    """A model that couldn't reach a host has stood up a container in its place, then reported success on that."""
    if not CONTAINER_START.search(cmd) or not ssh_failed_this_turn(transcript_path):
        return None
    return ("Blocked: ssh couldn't reach the host, and a container here wouldn't be that host. Don't try to stand one in. "
            "Report that the host is unreachable, with the error you saw, and stop. If the user asks for a container, they'll say so.")


# sed -i s/a/b/ on one file changes every line that matches and never says how many. Across many files, or with g, it's bulk work.
ONE_FILE_SED = re.compile(r"^(?:cd\s+\S+\s*&&\s*)?(?:sudo(?:\s+-A)?\s+)?sed\s+-i\S*\s+(?:-e\s+)?(['\"])s(.)(?:(?!\2).)*\2(?:(?!\2).)*\2([a-zA-Z]*)\1\s+(\S+)\s*$")


def one_file_sed_verdict(cmd):
    m = ONE_FILE_SED.match(cmd.strip())
    if not m or "g" in m.group(3):
        return None
    return (f"Blocked: this would change every line that matches, without saying how many. Use the exact text, which refuses if it isn't unique, then shows the diff:\n"
            f"edit_file {m.group(4)} <<'EDIT'\n@@old\nthe exact line\n@@new\nwhat it becomes\n@@end\nEDIT\n"
            "If every match really should change, add g to your sed.")


def script_on_path_verdict(cmd):
    if "#!" not in cmd or not SCRIPT_ON_PATH.search(cmd):
        return None
    return ("Blocked: a command that should last goes through the gate, not straight onto PATH. Write the script to a file in this directory, then run:\n"
            "sakura-tool keep NAME ./FILE --about \"one line\" <<'CHECK'\nprintf 'input\\n' | NAME | grep -qx 'expected'\nCHECK\n"
            "It's on PATH in later sessions after that. If the user named this exact path, write the file elsewhere and cp it there.")


def coordinator_verdict(cmd):
    """Why a coordinator can't run this, or None. An allow-list, because shell has too many ways to write a file."""
    no = COORDINATOR_NO
    # A heredoc's body is text, and it can only reach a command that passes the checks below.
    bare = re.sub(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?(?:\n\s*\2\s*(?:\n|$)|\Z)", "\n", cmd, flags=re.S)
    bare = re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", "''", bare)  # what's quoted is an argument, not shell syntax
    bare = re.sub(r"\d?>\s*/dev/null|2>&1", " ", bare)
    if WRITES.search(bare) or "$(" in bare or "`" in bare:
        return no
    for part in re.split(r"&&|\|\||;|\||\n", bare):
        words = part.split()
        if not words:
            continue
        head = os.path.basename(words[0])
        if head == "git":
            sub = next((w for w in words[1:] if not w.startswith("-")), "")
            if sub in COORDINATOR_GIT and not (sub in ("branch", "tag") and len(words) > 2):
                continue
            if sub == "remote" and words[2:] in ([], ["-v"]):
                continue
            return no
        if head == "sakura-tool" and words[1:] == ["list"]:
            continue
        if head == "rag" and words[1:2] in (["search"], ["status"]):
            continue
        if head == "pa" and words[1:2] in (["brief"], ["list"], ["roles"], ["standup"]):
            continue
        if head == "sed" and "-n" in words and not any(w.startswith("-i") for w in words):
            continue
        if head not in COORDINATOR_OK:
            return no
    return None


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") not in ("Bash", "shell", "exec_command", "local_shell"):
        return
    cmd = (data.get("tool_input") or {}).get("command")
    if isinstance(cmd, list):
        cmd = " ".join(shlex.quote(c) for c in cmd)
    cmd = cmd or ""
    reason = verdict(cmd)
    if not reason and os.environ.get("SAKURA_COORDINATOR"):
        reason = coordinator_verdict(cmd)
    if not reason:
        reason = script_on_path_verdict(cmd) or big_cat_verdict(cmd, data.get("cwd")) or packages_verdict(cmd) or overwrite_verdict(cmd, data.get("cwd")) or stand_in_verdict(cmd, data.get("transcript_path")) \
            or ssh_around_verdict(cmd, data.get("transcript_path")) or keep_around_verdict(cmd, data.get("transcript_path")) or one_file_sed_verdict(cmd)
    if not reason and READS_PASSWORD.search(cmd):
        reason = PASSWORD_NO
    if not reason and os.environ.get("SAKURA_WORKER") and (MAIL_SEND.search(cmd) or MAIL_OTHER.search(cmd)):
        reason = WORKER_NO_MAIL
    if not reason and MAIL_SEND.search(cmd) and ASKED_FOR_DRAFT.search(this_turn(data.get("transcript_path"))[0]):
        reason = DRAFT_NO
    if not reason and MAIL_OTHER.search(cmd) and not os.environ.get("SAKURA_WORKER"):
        asked = this_turn(data.get("transcript_path"))[0].lower()
        if not re.search(r"\b(?:sendmail|postfix|exim|mailutils|msmtp|mutt|mailx|smtp)\b", asked):
            reason = USE_HIMALAYA
    if not reason and os.environ.get("SAKURA_WORKER") and PA_STANDING.search(cmd):
        reason = WORKER_NO_STANDING
    if not reason and os.environ.get("SAKURA_WORKER") and GIT_PUSH.search(cmd) and "push" not in this_turn(data.get("transcript_path"))[0].lower():
        reason = WORKER_NO_PUSH
    if not reason and os.environ.get("SAKURA_WORKER") and re.search(r"\bsakura-worker\b", cmd):
        reason = "You're a worker, so you can't start another one. Do the work yourself, or report that it's too big."
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))


def script_on_path_selftest():
    deny = ["cat > /usr/local/bin/x <<'E'\n#!/bin/sh\necho\nE", "sudo tee /usr/local/bin/x > /dev/null <<'E'\n#!/bin/sh\nE",
            "printf '#!/bin/sh\\n' > ~/.local/bin/x", "cat >> $HOME/bin/x <<'E'\n#!/bin/sh\nE", "tee -a /home/u/.local/bin/x <<'E'\n#!/bin/sh\nE",
            "sudo bash -c 'cat > /usr/bin/x << \"I\"\n#!/bin/sh\nI'"]
    allow = ["cat > ./x <<'E'\n#!/bin/sh\nE", "cp x /usr/local/bin/x", "curl -fsSL https://e/x -o ~/.local/bin/x", "cat /usr/local/bin/x",
             "sudo install -m755 x /usr/local/bin/x", "echo 1 > /tmp/bin/x", "cat > /tmp/x <<'E'\n#!/bin/sh\nls /usr/local/bin/x\nE", "sakura-tool keep x ./x --about y --check z"]
    bad = 0
    for c in deny:
        if not script_on_path_verdict(c):
            print("should block:", c)
            bad += 1
    for c in allow:
        if script_on_path_verdict(c):
            print("should allow:", c)
            bad += 1
    return bad, len(deny) + len(allow)


def coordinator_selftest():
    allow = ["git status", "git log --oneline -5", "git diff HEAD~1 | head -50", "sed -n '1,20p' a.py", "rg foo src",
             "sakura-worker --verify 'pytest -k x' 'fix > and < in parser'", "cat a 2>/dev/null", "sakura-memory state note 'done > ok'",
             "cd src && ls", "git remote -v", "sakura-worker <<'JOB'\nverify: python3 -c 'import a; assert a.f() > 1'\nscope: a.py\n\nfix f() > g(); rm -rf x\nJOB",
             'sakura-worker --verify "python3 -c \\"assert 1 > 0\\"" brief',  "find . -name '*.py'", "git branch", "sakura-tool list", "view_file a.py 1 50", "rag search 'where is x'"]
    deny = ["sed -i s/a/b/ f", "echo x > f", "rm -rf build", "python3 a.py", "git commit -am x", "git push", "tee f", "cat a > b",
            "find . -delete", "find . -exec rm {} +", "ls; rm f", "echo $(rm f)", "git branch -D main", "git tag v1", "cp a b", "npm test",
            "git remote add x y", "ls && touch f", "cat a | sh", "cat > f <<'E'\nhello\nE", "python3 <<'E'\nprint(1)\nE",
            "sakura-worker <<'J'\nbrief\nJ\nrm f",
            "sakura-tool keep a ./a --about x --check y", "sakura-tool remove a", "sakura-tool check", "sakura-tool list; rm f", "edit_file a <<'E'\n@@old\nx\n@@new\ny\n@@end\nE", "rag index ~/docs", "rag forget ~/docs"]
    bad = 0
    for c in allow:
        if coordinator_verdict(c):
            bad += 1
            print("coordinator should allow:", c)
    for c in deny:
        if not coordinator_verdict(c):
            bad += 1
            print("coordinator should deny:", c)
    return bad, len(allow) + len(deny)


def selftest():
    deny = [
        'xdg-open "https://nobeldahal.com.np/writing" &',
        'curl -s "https://nobeldahal.com.np/writing"',
        'curl -sL https://laravel.com/docs/start | grep -E "<title>|LTS"',
        'curl -s "https://en.wikipedia.org/wiki/Prime_Minister_of_Nepal_(current)" | strings | head -40',
        'curl -s "https://html.duckduckgo.com/html/?q=nepal+pm"',
        'wget -qO- https://www.google.com/search?q=laravel+lts',
    ]
    allow = [
        "ls -la",
        "grep -r foo .",
        'curl -s https://api.github.com/repos/laravel/laravel/releases/latest',
        'curl -s https://repo.packagist.org/p2/laravel/framework.json | jq .',
        'curl -sL https://nobeldahal.com.np/feed.xml',
        'curl -fsSL https://claude.com/install.sh | bash',
        'curl -o out.tar.gz https://example.com/release',
        'curl -I https://laravel.com',
        'curl -X POST -d "{}" https://example.com/hook',
        'curl http://localhost:8000/health',
        'fetch_url "https://laravel.com/docs"',
    ]
    bad = 0
    for c in deny:
        if not verdict(c):
            print("SHOULD DENY:", c); bad += 1
    for c in allow:
        if verdict(c):
            print("SHOULD ALLOW:", c, "->", verdict(c)[:60]); bad += 1
    cbad, ctotal = coordinator_selftest()
    sbad, stotal = script_on_path_selftest()
    bad += cbad + sbad
    total = len(deny) + len(allow) + ctotal + stotal
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "big"), "w") as f:
            f.write("x" * (BIG_FILE + 1))
        with open(os.path.join(d, "small"), "w") as f:
            f.write("x")
        with open(os.path.join(d, "long"), "w") as f:
            f.write("x\n" * 50)
        item = lambda p: json.dumps({"type": "response_item", "payload": p}) + "\n"
        say = lambda t: item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": t}]})
        ssh_call = item({"type": "function_call", "call_id": "1", "arguments": '{"cmd":"ssh dead uptime"}'})
        with open(os.path.join(d, "failed"), "w") as f:
            f.write(say("restart nginx on dead") + ssh_call + item({"type": "function_call_output", "call_id": "1", "output": "Process exited with code 255\nOutput: refused"}))
        with open(os.path.join(d, "worked"), "w") as f:
            f.write(say("go") + ssh_call + item({"type": "function_call_output", "call_id": "1", "output": "Process exited with code 0"}))
        with open(os.path.join(d, "earlier"), "w") as f:
            f.write(say("restart nginx on dead") + ssh_call + item({"type": "function_call_output", "call_id": "1", "output": "exited with code 255"}) + say("now start a test container"))
        failed_at = os.path.join(d, "failed")
        for c, want in (("ssh -i /tmp/other dead uptime", True), ("ssh -p 2222 dead uptime", True), ("ssh -o Port=2222 dead", True), ("ssh -o IdentityFile=/k dead", True), ("sed -i s/1/2/ ~/.ssh/config", True), ("echo x >> ~/.ssh/config", True),
                        ("ssh -v dead uptime", False), ("ssh dead uptime", False), ("cat ~/.ssh/config", False), ("ls /tmp > out.txt", False)):
            total += 1
            if bool(ssh_around_verdict(c, failed_at)) != want:
                bad += 1
                print("ssh_around wrong:", c)
        with open(os.path.join(d, "named"), "w") as f:
            f.write(say("restart nginx on dead, and try port 2222 if that fails") + ssh_call + item({"type": "function_call_output", "call_id": "1", "output": "exited with code 255"}))
        total += 1
        if ssh_around_verdict("ssh -p 2222 dead uptime", os.path.join(d, "named")):
            bad += 1
            print("ssh_around blocked a port the user named")
        for c, want in (("sed -i 's/a/b/' f.py", True), ("cd /x && sed -i 's/a/b/' f.py", True), ("sed -i 's/a/b/g' f.py", False), ("sed -i 's/a/b/' f.py g.py", False), ("sed -n '1,2p' f", False), ("sed -i '/x/d' f", False)):
            total += 1
            if bool(one_file_sed_verdict(c)) != want:
                bad += 1
                print("sed wrong:", c)
        with open(os.path.join(d, "keeping"), "w") as f:
            f.write(say("make a tool upcase and keep it") + item({"type": "function_call", "call_id": "2", "arguments": '{"cmd":"sakura-tool keep upcase ./upcase"}'}))
        for c, at, want in (("sudo mv ./upcase /usr/local/bin/upcase", "keeping", True), ("cp upcase ~/.local/bin/upcase", "keeping", True), ("mv a b", "keeping", False), ("cp x /usr/local/bin/x", "worked", False)):
            total += 1
            if bool(keep_around_verdict(c, os.path.join(d, at))) != want:
                bad += 1
                print("keep_around wrong:", c)
        run = "docker run -d -p 1:80 nginx"
        for got, want in ((stand_in_verdict(run, os.path.join(d, "failed")), True), (stand_in_verdict("sudo -A docker compose up -d", os.path.join(d, "failed")), True),
                          (stand_in_verdict(run, os.path.join(d, "worked")), False), (stand_in_verdict(run, os.path.join(d, "earlier")), False),
                          (stand_in_verdict("docker ps", os.path.join(d, "failed")), False), (stand_in_verdict(run, None), False)):
            total += 1
            if bool(got) != want:
                bad += 1
                print("stand_in wrong:", got, want)
        for got, want in ((overwrite_verdict("cat > long <<'E'\nx\nE", d), True), (overwrite_verdict("cat > small <<'E'\nx\nE", d), False), (overwrite_verdict("cat > new <<'E'\nx\nE", d), False), (overwrite_verdict("cat >> long <<'E'\nx\nE", d), False),
                          (overwrite_verdict("tee long <<'E'\nx\nE", d), True), (overwrite_verdict("cat long", d), False),
                          (packages_verdict("pip install x --break-system-packages"), True), (packages_verdict("pip install x"), False),
                          (big_cat_verdict("cat big", d), True), (big_cat_verdict("cat small", d), False), (big_cat_verdict("cat big | head", d), False), (big_cat_verdict("cat nope", d), False),
                          (READS_PASSWORD.search("pass show email/me"), True), (READS_PASSWORD.search("/tmp/x/bin/pass show email/me"), True), (READS_PASSWORD.search("cat ~/.password-store/email/me.gpg"), True), (READS_PASSWORD.search("pass insert email/me"), True),
                          (READS_PASSWORD.search("grep pass config.toml"), False), (READS_PASSWORD.search("pytest --pass show"), False), (READS_PASSWORD.search("sakura-mail-setup check me"), False),
                          (ASKED_FOR_DRAFT.search("Draft an email to bob and show it to me before anything goes out"), True), (ASKED_FOR_DRAFT.search("Email bob with the subject Lunch"), False),
                          (PA_STANDING.search("pa autoreply on 'busy'"), True), (PA_STANDING.search("pa job every day 7am: x"), True), (PA_STANDING.search("crontab -e"), True), (PA_STANDING.search("pa brief"), False), (PA_STANDING.search("pa remind in 1 hour x"), False),
                          (MAIL_OTHER.search('echo x | mail -s hi a@b.c'), True), (MAIL_OTHER.search("apt-get install -y mailutils"), True), (MAIL_OTHER.search("sudo service postfix start"), True), (MAIL_OTHER.search("sudo postconf -e x"), True), (MAIL_OTHER.search("python3 -c 'import smtplib'"), True), (MAIL_OTHER.search("curl smtp://x"), True),
                          (MAIL_OTHER.search('printf "EHLO x\\r\\nMAIL FROM:<a>" | nc -w 5 127.0.0.1 3026'), True), (MAIL_OTHER.search("telnet smtp.gmail.com 587"), True), (MAIL_OTHER.search("nc -z db.local 5432"), False),
                          (MAIL_OTHER.search("cat mail.py"), False), (MAIL_OTHER.search("python3 evals/mail.py"), False), (MAIL_OTHER.search("ls ~/mail/inbox"), False), (MAIL_OTHER.search("grep -r email src"), False),
                          (MAIL_SEND.search("himalaya message send < m.txt"), True), (MAIL_SEND.search("himalaya message compose --to a@b --body x --send"), True), (MAIL_SEND.search("himalaya -a x message reply 3 --body y --send"), True), (MAIL_SEND.search("himalaya smtp send m.eml"), True), (MAIL_SEND.search("himalaya message compose --to a@b --body x"), False), (MAIL_SEND.search("himalaya envelope list"), False), (MAIL_SEND.search("himalaya message read 3"), False)):
            total += 1
            if bool(got) != want:
                bad += 1
                print("wrong:", got, want)
    print(f"tool_guard selftest: {total - bad}/{total} ok")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
