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
    reason = verdict(cmd or "")
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))


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
    print(f"tool_guard selftest: {len(deny) + len(allow) - bad}/{len(deny) + len(allow)} ok")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
