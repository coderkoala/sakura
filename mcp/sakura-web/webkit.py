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


def _get_full(url, timeout=20, data=None, headers=None):
    """Fetch a URL, following redirects. Returns (text, final_url, content_type)."""
    h = {"User-Agent": UA, "Accept": "text/html,application/xml,application/json,*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        ctype = (r.headers.get_content_type() or "").lower()
        return r.read().decode(charset, "replace"), r.geturl(), ctype


def _get(url, timeout=20, data=None, headers=None):
    return _get_full(url, timeout=timeout, data=data, headers=headers)[0]


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


def _wd_json(params):
    return json.loads(_get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(params), timeout=15))


# Role phrase -> Wikidata property. P6 = head of government, P35 = head of state.
_LEADER_ROLES = [
    (re.compile(r"\b(prime minister|pm|premier|chancellor|head of government|taoiseach)\b", re.I), "P6", "head of government"),
    (re.compile(r"\b(president|head of state)\b", re.I), "P35", "head of state"),
    (re.compile(r"\b(king|queen|monarch|emperor)\b", re.I), "P35", "monarch / head of state"),
]
_LEADER_Q = re.compile(
    r"\b(?:who(?:'s| is| are)?|current|now)\b.*?\b(prime minister|pm|premier|chancellor|president|king|queen|monarch|head of (?:state|government))\b",
    re.I,
)


def country_leader(query):
    """Answer 'who is the current <role> of <place>' from Wikidata (authoritative, not bot-blocked).

    Returns formatted text, or None if the query isn't a leader question or the lookup fails.
    """
    if not _LEADER_Q.search(query):
        return None
    prop = role_label = None
    for rx, p, lbl in _LEADER_ROLES:
        if rx.search(query):
            prop, role_label = p, lbl
            break
    if not prop:
        return None
    # Place = the noun phrase after the last "of" (… prime minister OF nepal).
    m = re.search(r"\bof\s+([A-Za-z][A-Za-z .'-]+?)\s*[?.!]*$", query.strip(), re.I)
    place = (m.group(1) if m else "").strip()
    if not place:
        return None
    try:
        hits = _wd_json({"action": "wbsearchentities", "search": place, "language": "en",
                         "format": "json", "limit": "1"}).get("search", [])
        if not hits:
            return None
        place_qid = hits[0]["id"]
        place_label = hits[0].get("label", place)
        claims = _wd_json({"action": "wbgetclaims", "entity": place_qid, "property": prop,
                           "format": "json"}).get("claims", {}).get(prop, [])
        if not claims:
            return None

        def rank_key(cl):
            rank = {"preferred": 0, "normal": 1, "deprecated": 2}.get(cl.get("rank"), 1)
            has_end = "P582" in cl.get("qualifiers", {})  # end date => former
            start = ""
            if "P580" in cl.get("qualifiers", {}):
                try:
                    start = cl["qualifiers"]["P580"][0]["datavalue"]["value"]["time"]
                except Exception:
                    start = ""
            # current first: preferred rank, then no end-date, then most recent start
            return (rank, 1 if has_end else 0, _neg_time(start))

        claims = [c for c in claims if c.get("mainsnak", {}).get("datavalue")]
        if not claims:
            return None
        claims.sort(key=rank_key)
        cur = claims[0]
        person_qid = cur["mainsnak"]["datavalue"]["value"]["id"]
        ent = _wd_json({"action": "wbgetentities", "ids": person_qid, "props": "labels|descriptions|sitelinks",
                        "languages": "en", "format": "json"})["entities"][person_qid]
        name = ent.get("labels", {}).get("en", {}).get("value", person_qid)
        desc = ent.get("descriptions", {}).get("en", {}).get("value", "")
        since = ""
        if "P580" in cur.get("qualifiers", {}):
            try:
                since = cur["qualifiers"]["P580"][0]["datavalue"]["value"]["time"].lstrip("+")[:10]
            except Exception:
                since = ""
        wiki_url = ""
        title = ent.get("sitelinks", {}).get("enwiki", {}).get("title")
        if title:
            wiki_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        out = f"The current {role_label} of {place_label} is {name}"
        if since:
            out += f" (in office since {since})"
        out += "."
        if desc:
            out += f" {name}: {desc}."
        out += "\n\nSource: Wikidata https://www.wikidata.org/wiki/" + place_qid
        if wiki_url:
            out += f" · {wiki_url}"
        out += ("\n(Wikidata is community-maintained and usually current within days of a change; "
                "verify against the linked page if this is a very recent transition.)")
        return out
    except Exception:
        return None


def _neg_time(t):
    """Sort key helper: later ISO times sort first."""
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in t) if t else "~"


def _ddg_html_results(query, max_results):
    """Scrape the DuckDuckGo HTML endpoint. Returns (results, blocked)."""
    body = urllib.parse.urlencode({"q": query, "kl": "us-en"}).encode()
    try:
        html = _get("https://html.duckduckgo.com/html/", data=body)
    except Exception:
        return [], True
    # DDG serves an anti-bot / CAPTCHA page to scrapers from many hosts; detect it so we fall back
    # instead of reporting "no results" (which makes a weak model hallucinate or hand-roll curl).
    if "anomaly-modal" in html or "Verifying your browser" in html or 'class="result__a"' not in html:
        return [], True
    results = []
    for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
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
    return results, False


def _ddg_instant(query):
    """DuckDuckGo Instant Answer JSON API (not bot-blocked). Returns a short text answer or None."""
    try:
        api = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": "1", "no_redirect": "1"}
        )
        d = json.loads(_get(api, timeout=12))
    except Exception:
        return None
    for key in ("Answer", "AbstractText", "Definition"):
        val = (d.get(key) or "").strip()
        if val:
            src = d.get("AbstractURL") or d.get("DefinitionURL") or "https://duckduckgo.com"
            return f"{val}\nSource: {src}"
    return None


def web_search(query, max_results=8):
    max_results = max(1, min(int(max_results or 8), 15))
    parts = []

    # Wikipedia is the PRIMARY source: reliable and never CAPTCHA-blocked, unlike the search engines.
    wiki = wikipedia(query)
    if wiki and "No Wikipedia article" not in wiki:
        parts.append(wiki)

    # A current office-holder question gets the authoritative Wikidata answer.
    leader = country_leader(query)
    if leader:
        parts.append(leader)

    # Supplement with real engine results only when this host isn't being blocked.
    results, blocked = _ddg_html_results(query, max_results)
    if results:
        lines = ["Other web results:"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['url']}")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
        parts.append("\n".join(lines))
    elif not parts:
        instant = _ddg_instant(query)
        if instant:
            parts.append("DuckDuckGo Instant Answer:\n" + instant)

    if not parts:
        return ("Wikipedia had no article and the search engines (DuckDuckGo, SearXNG) are serving "
                "anti-bot/CAPTCHA pages to this host. Do NOT hand-roll curl/grep on a search engine — it "
                "will not work. Try `wikipedia` with a cleaner query, or `fetch_url` on a specific known URL.")
    if blocked:
        parts.append("(Search engines are blocked from this host — the above is from Wikipedia/Wikidata, "
                     "which are authoritative for facts. For docs, fetch_url an official docs URL directly.)")
    parts.append("Cite the URL(s) you used.")
    return "\n\n".join(parts)


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
    """Search a domain's curated authoritative sites. Uses the engine when reachable; when engines are
    CAPTCHA-blocked it hands back the authoritative URLs to fetch_url directly (those sites aren't blocked)."""
    sites = curated_sites(domain)
    if not sites:
        avail = ", ".join(sorted(_SOURCES.get("domains", {})))
        return f"No curated sources for '{domain}'. Available domains: {avail}. Falling back to a plain web_search:\n\n" + web_search(query, max_results)
    scope = " OR ".join(f"site:{s}" for s in sites[:12])
    results, blocked = _ddg_html_results(f"({scope}) {query}", max_results)
    header = f"Curated '{domain}' sources: {', '.join(sites[:12])}\n\n"
    if results:
        lines = [f"Scoped search results for: {query}"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['url']}")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
        lines.append("\nCite the URL(s) you used.")
        return header + "\n".join(lines)
    # Engines are blocking this host: these authoritative sites are NOT blocked — fetch them directly.
    sites_list = "\n".join(f"- https://{s}" for s in sites[:12])
    wiki = wikipedia(query)
    wiki_block = ("" if "No Wikipedia article" in wiki else "\nWikipedia (for background):\n" + wiki + "\n")
    return (header + "Web search engines are CAPTCHA-blocking this host, so a scoped search can't run. "
            "These authoritative sources are NOT blocked — `fetch_url` the most relevant one directly "
            f"for \"{query}\" (try the site's /search or /docs path, or a likely doc URL):\n" + sites_list
            + "\n" + wiki_block + "\nDo NOT curl/grep a search engine — it will not work.")


def _discover_feed(html, base_url):
    """Return an absolute RSS/Atom feed URL advertised in an HTML <head>, or None."""
    for m in re.finditer(r"<link\b[^>]*>", html[:20000], re.I):
        tag = m.group(0)
        if "alternate" in tag.lower() and re.search(r"type\s*=\s*['\"]?application/(rss|atom)\+xml", tag, re.I):
            href = re.search(r"href\s*=\s*['\"]([^'\"]+)['\"]", tag, re.I)
            if href:
                return urllib.parse.urljoin(base_url, unescape(href.group(1)))
    return None


def _looks_like_feed(text, ctype):
    if any(k in ctype for k in ("xml", "rss", "atom")):
        return True
    head = text.lstrip()[:200].lower()
    return head.startswith("<?xml") or "<rss" in head or "<feed" in head


def _render_feed(xml_text, url, max_items=30):
    """Render an RSS 2.0 or Atom feed as structured, readable entries."""
    import xml.etree.ElementTree as ET

    def strip_ns(t):
        return t.split("}", 1)[1] if "}" in t else t

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None  # not parseable as XML; let the caller fall back to text

    def find_text(node, *names):
        for child in node:
            if strip_ns(child.tag) in names and child.text:
                return child.text.strip()
        return ""

    def link_of(node):
        for child in node:
            if strip_ns(child.tag) == "link":
                return (child.get("href") or child.text or "").strip()
        return ""

    tag = strip_ns(root.tag).lower()
    channel = next((c for c in root if strip_ns(c.tag) == "channel"), root)
    title = find_text(channel, "title")
    desc = find_text(channel, "description", "subtitle")
    items = [c for c in channel if strip_ns(c.tag) in ("item", "entry")]
    # Not actually a feed (some other XML that merely parsed): let fetch_url fall back to text.
    if tag not in ("rss", "feed") and not items:
        return None

    lines = [f"Feed: {title}".rstrip()]
    if desc:
        lines.append(desc)
    lines.append(f"{len(items)} entries\n")
    for it in items[:max_items]:
        t = find_text(it, "title") or "(untitled)"
        link = link_of(it)
        date = find_text(it, "pubDate", "updated", "published", "date")
        summary = find_text(it, "description", "summary", "content")
        summary = re.sub(r"<[^>]+>", "", unescape(summary)).strip()
        if len(summary) > 500:
            summary = summary[:500].rstrip() + "…"
        block = f"## {t}"
        if date:
            block += f"\n_{date}_"
        if link:
            block += f"\n{link}"
        if summary:
            block += f"\n\n{summary}"
        lines.append(block)
    extra = f"\n\n[{len(items) - max_items} more entries not shown]" if len(items) > max_items else ""
    return f"Source: {url} (RSS/Atom feed)\n\n" + "\n\n".join(lines) + extra


def fetch_url(url, max_chars=20000):
    if not re.match(r"^https?://", url):
        return "Error: url must start with http:// or https://"
    max_chars = max(500, min(int(max_chars or 20000), 50000))
    raw, final_url, ctype = _get_full(url, timeout=25)

    # A feed (direct, or a page that is really XML) renders as structured entries.
    if _looks_like_feed(raw, ctype):
        rendered = _render_feed(raw, final_url)
        if rendered:
            clipped = rendered[:max_chars]
            suffix = "" if len(rendered) <= max_chars else f"\n\n[truncated at {max_chars} chars]"
            return clipped + suffix

    is_html = "<" in raw[:2000]
    text = html_to_text(raw) if is_html else raw
    clipped = text[:max_chars]
    suffix = "" if len(text) <= max_chars else f"\n\n[truncated at {max_chars} chars]"

    # Point the model at the feed when the page advertises one: one fetch reads every entry,
    # which is what a JS-rendered (SPA) blog or news index needs — the HTML body is often thin.
    hint = ""
    if is_html:
        feed = _discover_feed(raw, final_url)
        if feed:
            hint = f"\n\n[This page advertises a feed: {feed} — fetch_url it to read all entries at once.]"
    return f"Source: {final_url}\n\n{clipped}{suffix}{hint}"


# ── Version grounding ─────────────────────────────────────────────────────────
# A current fact that changes over time includes the version of every tool and framework in
# use. The local model's training is stale, so a question about Laravel must be answered for the
# version THIS project pins (e.g. 13), not the model's training-era 8. We read the project's own
# manifests and the installed CLIs, and inject the real versions.

# alias(es) in a prompt -> (manifest keys to match, CLI to probe for --version)
_TOOL_TABLE = {
    "php": (["php"], ["php", "-r", "echo PHP_VERSION;"]),
    "laravel": (["laravel/framework", "laravel/laravel"], None),
    "octane": (["laravel/octane"], None),
    "livewire": (["livewire/livewire"], None),
    "symfony": (["symfony/framework-bundle", "symfony/symfony"], None),
    "composer": ([], ["composer", "--version"]),
    "phpunit": (["phpunit/phpunit"], None),
    "pest": (["pestphp/pest"], None),
    "node": ([], ["node", "--version"]),
    "npm": ([], ["npm", "--version"]),
    "vue": (["vue"], None),
    "vite": (["vite"], None),
    "react": (["react"], None),
    "next": (["next"], None),
    "nuxt": (["nuxt"], None),
    "svelte": (["svelte"], None),
    "angular": (["@angular/core"], None),
    "typescript": (["typescript"], ["tsc", "--version"]),
    "tailwind": (["tailwindcss"], None),
    "eslint": (["eslint"], None),
    "python": ([], ["python3", "--version"]),
    "django": (["django", "Django"], None),
    "flask": (["flask", "Flask"], None),
    "fastapi": (["fastapi"], None),
    "pandas": (["pandas"], None),
    "numpy": (["numpy"], None),
    "pytest": (["pytest"], None),
    "ruby": ([], ["ruby", "--version"]),
    "rails": (["rails"], None),
    "go": (["go"], ["go", "version"]),
    "rust": ([], ["rustc", "--version"]),
    "cargo": ([], ["cargo", "--version"]),
    "git": ([], ["git", "--version"]),
    "docker": ([], ["docker", "--version"]),
    "ollama": ([], ["ollama", "--version"]),
}
_TECH = re.compile(r"\b(" + "|".join(re.escape(k) for k in _TOOL_TABLE) + r"|version|upgrade|deprecat|latest release)\b", re.I)


def _read_manifests(cwd):
    """Collect {dependency: version_spec} from the manifests in cwd (walk up a few levels)."""
    import os
    deps = {}
    d = os.path.abspath(cwd or ".")
    for _ in range(4):
        def load_json(name):
            try:
                return json.load(open(os.path.join(d, name), encoding="utf-8"))
            except Exception:
                return None
        cj = load_json("composer.json")
        if cj:
            deps.update(cj.get("require", {}))
            deps.update(cj.get("require-dev", {}))
        pj = load_json("package.json")
        if pj:
            deps.update(pj.get("dependencies", {}))
            deps.update(pj.get("devDependencies", {}))
        for fn in ("pyproject.toml", "Cargo.toml"):
            p = os.path.join(d, fn)
            if os.path.exists(p):
                try:
                    import tomllib
                    t = tomllib.load(open(p, "rb"))
                    if fn == "pyproject.toml":
                        for dep in (t.get("project", {}).get("dependencies", []) or []):
                            m = re.match(r"([A-Za-z0-9_.\-]+)\s*(.*)", dep)
                            if m:
                                deps[m.group(1)] = m.group(2) or "*"
                    else:
                        for k, v in (t.get("dependencies", {}) or {}).items():
                            deps[k] = v if isinstance(v, str) else (v.get("version", "*") if isinstance(v, dict) else "*")
                except Exception:
                    pass
        gm = os.path.join(d, "go.mod")
        if os.path.exists(gm):
            try:
                for line in open(gm, encoding="utf-8"):
                    m = re.match(r"\s*go\s+(\d[\d.]+)", line)
                    if m:
                        deps["go"] = m.group(1)
            except Exception:
                pass
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return deps


def _cli_version(cmd):
    import shutil
    import subprocess
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        text = (out.stdout or out.stderr or "").strip()
        m = re.search(r"\d+\.\d+(\.\d+)?", text)
        return m.group(0) if m else (text.splitlines()[0][:40] if text else None)
    except Exception:
        return None


# tool -> (registry, identifier) for the LATEST published version. Authoritative, keyless, not CAPTCHA'd.
_REGISTRY = {
    "laravel": ("packagist", "laravel/framework"),
    "symfony": ("packagist", "symfony/symfony"),
    "livewire": ("packagist", "livewire/livewire"),
    "composer": ("gh", "composer/composer"),
    "php": ("gh", "php/php-src"),
    "vue": ("npm", "vue"),
    "react": ("npm", "react"),
    "next": ("npm", "next"),
    "nuxt": ("npm", "nuxt"),
    "svelte": ("npm", "svelte"),
    "angular": ("npm", "@angular/core"),
    "typescript": ("npm", "typescript"),
    "tailwind": ("npm", "tailwindcss"),
    "eslint": ("npm", "eslint"),
    "vite": ("npm", "vite"),
    "node": ("gh", "nodejs/node"),
    "npm": ("npm", "npm"),
    "django": ("pypi", "django"),
    "flask": ("pypi", "flask"),
    "fastapi": ("pypi", "fastapi"),
    "pandas": ("pypi", "pandas"),
    "numpy": ("pypi", "numpy"),
    "python": ("gh", "python/cpython"),
    "ruby": ("gh", "ruby/ruby"),
    "rails": ("gh", "rails/rails"),
    "go": ("goweb", ""),
    "golang": ("goweb", ""),
    "rust": ("gh", "rust-lang/rust"),
    "cargo": ("gh", "rust-lang/cargo"),
    "serde": ("crates", "serde"),
    "tokio": ("crates", "tokio"),
    "docker": ("gh", "moby/moby"),
    "kubernetes": ("gh", "kubernetes/kubernetes"),
    "k8s": ("gh", "kubernetes/kubernetes"),
    "ollama": ("gh", "ollama/ollama"),
    "postgres": ("gh", "postgres/postgres"),
    "postgresql": ("gh", "postgres/postgres"),
    "redis": ("gh", "redis/redis"),
    "nginx": ("gh", "nginx/nginx"),
}
_LATEST_Q = re.compile(r"\b(latest|current|newest|recent|up[- ]?to[- ]?date|lts|stable|which version|what version|version of)\b", re.I)


def _registry_latest(kind, ident):
    try:
        if kind == "packagist":
            d = json.loads(_get(f"https://repo.packagist.org/p2/{ident}.json", timeout=12))
            vers = [p["version"] for p in d["packages"][ident]]
            stable = [v for v in vers if not re.search(r"(dev|alpha|beta|rc)", v, re.I)]
            v = (stable or vers)[0]
            return v, f"https://packagist.org/packages/{ident}"
        if kind == "npm":
            d = json.loads(_get(f"https://registry.npmjs.org/{urllib.parse.quote(ident, safe='@/')}/latest", timeout=12))
            return d["version"], f"https://www.npmjs.com/package/{ident}"
        if kind == "pypi":
            d = json.loads(_get(f"https://pypi.org/pypi/{ident}/json", timeout=12))
            return d["info"]["version"], f"https://pypi.org/project/{ident}/"
        if kind == "crates":
            d = json.loads(_get(f"https://crates.io/api/v1/crates/{ident}", timeout=12))
            return d["crate"]["max_stable_version"], f"https://crates.io/crates/{ident}"
        if kind == "gh":
            try:
                d = json.loads(_get(f"https://api.github.com/repos/{ident}/releases/latest", timeout=12))
                tag = d.get("tag_name")
                if tag:
                    return tag, f"https://github.com/{ident}/releases/latest"
            except Exception:
                pass
            d = json.loads(_get(f"https://api.github.com/repos/{ident}/tags?per_page=20", timeout=12))
            tags = [t["name"] for t in d]
            stable = [t for t in tags if not re.search(r"(dev|alpha|beta|rc|pre)", t, re.I)]
            if stable or tags:
                return (stable or tags)[0], f"https://github.com/{ident}/tags"
        if kind == "goweb":
            txt = _get("https://go.dev/VERSION?m=text", timeout=12).splitlines()[0]
            return txt, "https://go.dev/dl/"
    except Exception:
        return None, None
    return None, None


def latest_version(prompt):
    """For 'what is the latest/current version of <tool>', return the authoritative published version."""
    if not _LATEST_Q.search(prompt):
        return None
    tool = next((name for name in _REGISTRY if re.search(r"\b" + re.escape(name) + r"\b", prompt, re.I)), None)
    if not tool:
        return None
    kind, ident = _REGISTRY[tool]
    ver, url = _registry_latest(kind, ident)
    if not ver:
        return None
    note = ""
    if re.search(r"\blts\b", prompt, re.I):
        note = (" (Note: not every project has a separate 'LTS' line — many just have fixed support windows per "
                "release; check the project's support policy page for dates.)")
    return (f"The latest published version of {tool} is {ver} (authoritative registry, fetched just now). "
            f"Answer from this, not from training.{note}\nSource: {url}")


def version_context(prompt, cwd="."):
    """Return version facts (project manifests + installed CLIs) for tools named in the prompt, or None."""
    if not _TECH.search(prompt):
        return None
    tools = [name for name in _TOOL_TABLE if re.search(r"\b" + re.escape(name) + r"\b", prompt, re.I)]
    deps = _read_manifests(cwd)
    lines = []
    seen = set()
    for name in tools:
        keys, cli = _TOOL_TABLE[name]
        ver = None
        src = ""
        for k in keys:
            for dk, dv in deps.items():
                if dk.lower() == k.lower():
                    ver, src = dv, "this project"
                    break
            if ver:
                break
        if not ver and cli:
            ver = _cli_version(cli)
            src = "installed" if ver else ""
        if ver and name not in seen:
            seen.add(name)
            lines.append(f"- {name}: {ver} ({src})")
    # If the prompt is techy but named no specific tool, surface the project's headline stack.
    if not lines and deps:
        for k in ("php", "laravel/framework", "laravel/octane", "vue", "react", "next", "django",
                  "rails", "go", "typescript"):
            for dk, dv in deps.items():
                if dk.lower() == k.lower():
                    lines.append(f"- {dk}: {dv} (this project)")
                    break
        lines = lines[:6]
    if not lines:
        return None
    return ("Version context for this project — answer for THESE versions, and use the matching official "
            "documentation; do NOT answer for an older version from training:\n" + "\n".join(lines))


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
