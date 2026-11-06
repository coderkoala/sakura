#!/usr/bin/env python3
"""webtiers — better search and fetching for webkit, built from local services. Standard library only.

Search goes to the local SearXNG. A page is read with a plain request, and only a page that came back empty because JavaScript
builds it goes on to headless Chromium. Both are optional: anything not installed (see sakura-web-setup) is skipped.

A site that refuses or challenges us is taken at its word. Nothing here retries it another way, disguises the request or solves
a check: it's reported as refused, and the model goes elsewhere or opens it in sakura-browser for the user to deal with.
Nothing here calls a third-party service except the sites themselves.
"""
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
DATA = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "sakura")
ENV_PYTHON = os.path.join(DATA, "webenv", "bin", "python")
SEARXNG = os.environ.get("SAKURA_SEARXNG_URL", "http://127.0.0.1:8888")
THIN_CHARS = 300

# What a page that's only a challenge says, and what an ordinary page can also carry, such as a contact form's widget.
CHALLENGE = re.compile(
    r"just a moment\.\.\.|cf-chl-|challenges\.cloudflare\.com|verifying you are human|verify you are human|are you a robot|"
    r"enable javascript and cookies|attention required! \| cloudflare|access denied</title>|request unsuccessful\. incapsula", re.I)
CAPTCHA_WIDGET = re.compile(r"g-recaptcha|h-captcha|hcaptcha\.com|datadome|px-captcha", re.I)
JS_SHELL = re.compile(r"you need to enable javascript|please enable javascript|requires javascript|<noscript>[^<]*javascript", re.I)
REFUSED_STATUS = {401, 403, 406, 429, 451, 503, 520, 521, 522, 523, 524, 525, 526}


def challenged(status, html, text=""):
    """The site refused us. A CAPTCHA script on a page that also has real content is only a contact form or a badge."""
    size = len(text.strip())
    return status in REFUSED_STATUS or (size < 1500 and bool(CHALLENGE.search(html[:200000]))) or (size < THIN_CHARS and bool(CAPTCHA_WIDGET.search(html[:200000])))


def thin(text, html):
    return len(text.strip()) < THIN_CHARS or (len(text.strip()) < 1500 and bool(JS_SHELL.search(html[:200000])))


def _heavy(args, stdin=None, timeout=45):
    """Run one step in the web environment. None if it isn't installed or the step failed."""
    if not os.path.exists(ENV_PYTHON):
        return None
    try:
        p = subprocess.run([ENV_PYTHON, "-I", os.path.join(HERE, "heavy.py")] + args, input=stdin, capture_output=True, text=True, timeout=timeout)
        out = json.loads(p.stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None
    return None if out.get("error") else out


def render(url):
    return _heavy(["render", url], timeout=60)


def extract(html):
    """The page's main text as markdown, or None if the extractor isn't there or found too little."""
    out = _heavy(["extract"], stdin=html, timeout=25)
    text = (out or {}).get("text") or ""
    return text if len(text.strip()) >= THIN_CHARS else None


# ── Search ────────────────────────────────────────────────────────────────────

def searxng(query, max_results=8, categories=None, time_range=None):
    """Results from the local SearXNG: [{"title", "url", "snippet", "date"}]. Empty if it's not there."""
    params = {"q": query, "format": "json"}
    if categories:
        params["categories"] = categories
    if time_range:
        params["time_range"] = time_range
    try:
        api = SEARXNG + "/search?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(api, timeout=15) as r:
            found = json.loads(r.read().decode("utf-8", "replace")).get("results") or []
    except Exception:
        return []
    return [{"title": x.get("title") or x["url"], "url": x["url"], "snippet": (x.get("content") or "").strip(), "date": x.get("publishedDate") or ""}
            for x in found if str(x.get("url", "")).startswith("http")][:max_results]
