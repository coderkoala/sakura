#!/usr/bin/env python3
"""webkit — shared, zero-dependency web-knowledge core for Sakura.

Used by both the sakura-web MCP server (server.py) and the web_search / fetch_url /
wikipedia shell CLIs (../../bin/). Stdlib only. Each function returns plain text
with source URLs so answers can be cited.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"


def log(*a):
    print("[sakura-web]", *a, file=sys.stderr, flush=True)


def _get(url, timeout=20, data=None, headers=None):
    h = {"User-Agent": UA, "Accept": "text/html,application/json,*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, "replace")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "head"):
            self.skip += 1
        if tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

    def text(self):
        t = "".join(self.out)
        t = re.sub(r"[ \t\f\v]+", " ", t)
        t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
        return t.strip()


def html_to_text(html):
    p = _Text()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.text()


def _ddg_decode(href):
    m = re.search(r"[?&]uddg=([^&]+)", href)
    if m:
        return urllib.parse.unquote(m.group(1))
    if href.startswith("//"):
        return "https:" + href
    return href


def web_search(query, max_results=8):
    max_results = max(1, min(int(max_results or 8), 15))
    body = urllib.parse.urlencode({"q": query, "kl": "us-en"}).encode()
    html = _get("https://html.duckduckgo.com/html/", data=body)
    results = []
    for m in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S
    ):
        url = _ddg_decode(unescape(m.group(1)))
        title = unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if not title or not url.startswith("http"):
            continue
        results.append({"title": title, "url": url})
        if len(results) >= max_results:
            break
    snips = [
        unescape(re.sub(r"<[^>]+>", "", s)).strip()
        for s in re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    ]
    for i, r in enumerate(results):
        if i < len(snips):
            r["snippet"] = snips[i]
    if not results:
        return "No results (DuckDuckGo returned nothing parseable). Try rephrasing."
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['url']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
    lines.append("\nCite the URL(s) you used.")
    return "\n".join(lines)


import os as _os

def _load_sources():
    try:
        with open(_os.path.join(_os.path.dirname(_os.path.realpath(__file__)), "sources.json")) as f:
            return json.load(f)
    except Exception:
        return {"domains": {}, "_personas": {}}


_SOURCES = _load_sources()


def curated_sites(domain):
    """Resolve a domain key or a persona name to its curated site list."""
    d = (domain or "").strip().lower()
    if d in _SOURCES.get("domains", {}):
        return _SOURCES["domains"][d]
    mapped = _SOURCES.get("_personas", {}).get(d)
    if mapped:
        return _SOURCES["domains"].get(mapped, [])
    return []


def curated_search(domain, query, max_results=8):
    """web_search scoped to a domain's (or persona's) curated authoritative sites."""
    sites = curated_sites(domain)
    if not sites:
        avail = ", ".join(sorted(_SOURCES.get("domains", {})))
        return f"No curated sources for '{domain}'. Available domains: {avail}. Falling back to a plain web_search:\n\n" + web_search(query, max_results)
    scope = " OR ".join(f"site:{s}" for s in sites[:12])
    scoped = f"({scope}) {query}"
    out = web_search(scoped, max_results)
    return f"Curated '{domain}' sources: {', '.join(sites[:12])}\n\n" + out


def fetch_url(url, max_chars=20000):
    if not re.match(r"^https?://", url):
        return "Error: url must start with http:// or https://"
    max_chars = max(500, min(int(max_chars or 20000), 50000))
    raw = _get(url, timeout=25)
    text = html_to_text(raw) if "<" in raw[:2000] else raw
    clipped = text[:max_chars]
    suffix = "" if len(text) <= max_chars else f"\n\n[truncated at {max_chars} chars]"
    return f"Source: {url}\n\n{clipped}{suffix}"


def wikipedia(query, sentences=6):
    api = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 1}
    )
    hits = json.loads(_get(api)).get("query", {}).get("search", [])
    if not hits:
        return f"No Wikipedia article found for: {query}"
    title = hits[0]["title"]
    summ = json.loads(
        _get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title))
    )
    extract = summ.get("extract", "")
    if sentences:
        parts = re.split(r"(?<=[.!?])\s+", extract)
        extract = " ".join(parts[: max(1, int(sentences))])
    page_url = summ.get("content_urls", {}).get("desktop", {}).get("page") or (
        "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    )
    return f"Wikipedia: {title}\n\n{extract}\n\nSource: {page_url}"


TOOLS = [
    {
        "name": "web_search",
        "description": "Search the live web via DuckDuckGo (no API key). Returns the top results with titles, snippets and source URLs. Use for current events, prices, releases and any fact that changes over time — then cite the URLs.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "1-15, default 8"},
            },
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch a web page (or raw text/JSON) and return its readable text content, HTML stripped. Use to read a source found via web_search before citing it.",
        "inputSchema": {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "description": "http(s) URL"},
                "max_chars": {"type": "integer", "description": "cap, default 20000"},
            },
        },
    },
    {
        "name": "wikipedia",
        "description": "Look up a topic on Wikipedia and return a current summary with the article URL to cite. Good for people, places, organisations and definitions.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Topic or title"},
                "sentences": {"type": "integer", "description": "summary length, default 6"},
            },
        },
    },
    {
        "name": "curated_search",
        "description": "Search only a domain's curated, authoritative sites (hacking refs, wikis, docs). Pass domain=one of: security, osint, reversing, forensics, networking, sysadmin, devops, database, programming, gaming, language, general — or your own persona name. Returns results with source URLs to cite.",
        "inputSchema": {
            "type": "object",
            "required": ["domain", "query"],
            "properties": {
                "domain": {"type": "string", "description": "domain key or persona name"},
                "query": {"type": "string", "description": "search query"},
                "max_results": {"type": "integer", "description": "1-15, default 8"},
            },
        },
    },
]
