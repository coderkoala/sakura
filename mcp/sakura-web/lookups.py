#!/usr/bin/env python3
"""lookups — generic, authoritative lookups for the grounding hook (stdlib only).

Replaces hand-made tables with lookups that work for ANY office or tool:
  officeholder(subject, role)  current holder of an office, from Wikidata's truthy values
                               (preferred rank, else normal) — the same semantics as SPARQL wdt:
  tool_latest(tool, ecosystem) latest published version from the right registry, or from every
                               registry that knows the name when the ecosystem is unknown
Both return text with sources, or None.

The HTTP layer is polite and resilient: Wikimedia gets a descriptive User-Agent (their policy;
anonymous browser UAs are throttled first), 429/5xx back off and retry, and GET responses are
cached on disk for 6 h so repeat questions cost nothing and survive a rate limit.
"""
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

UA_BROWSER = "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"
UA_BOT = "Sakura/0.1 (local personal agent; https://github.com/coderkoala/sakura)"
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "sakura-web")
CACHE_TTL = 6 * 3600


def _cache_path(url):
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ".json")


def get_json(url, timeout=12, ttl=CACHE_TTL, retries=3):
    path = _cache_path(url)
    try:
        st = os.stat(path)
        if time.time() - st.st_mtime < ttl:
            return json.load(open(path))
    except OSError:
        pass
    host = urllib.parse.urlparse(url).netloc
    ua = UA_BOT if ("wiki" in host or "github" in host) else UA_BROWSER
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                json.dump(data, open(path, "w"))
            except OSError:
                pass
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404 or e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(min(4, 0.75 * 2 ** attempt))
        except Exception as e:
            last = e
            time.sleep(0.5)
    # Rate-limited and out of retries: a stale cached answer beats none.
    try:
        return json.load(open(path))
    except Exception:
        raise last


# ── office-holders ────────────────────────────────────────────────────────────
# Plain-English office -> Wikidata property on the place/organisation entity.
ROLE_PROPS = [
    (r"prime minister|premier|chancellor|head of government|taoiseach|pm\b", "P6", "head of government"),
    (r"president|head of state", "P35", "head of state"),
    (r"king|queen|monarch|emperor|sultan|emir", "P35", "head of state"),
    (r"mayor|governor|first minister|chief minister|head of (the )?(city|province|state)", "P6", "head of government"),
    (r"ceo|chief executive", "P169", "chief executive officer"),
    (r"chair(man|woman|person)?\b", "P488", "chairperson"),
    (r"director", "P1037", "director/manager"),
    (r"capital", "P36", "capital"),
    (r"currency", "P38", "currency"),
]


def _wd(params):
    return get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"}))


def _truthy(entity_id, prop):
    claims = _wd({"action": "wbgetentities", "ids": entity_id, "props": "claims"})["entities"][entity_id]["claims"].get(prop, [])
    preferred = [c for c in claims if c.get("rank") == "preferred"]
    best = preferred or [c for c in claims if c.get("rank") == "normal"]
    out = []
    for c in best:
        dv = c["mainsnak"].get("datavalue", {}).get("value")
        if isinstance(dv, dict) and "id" in dv:
            since = ""
            q = c.get("qualifiers", {}).get("P580")
            if q:
                try:
                    since = q[0]["datavalue"]["value"]["time"].lstrip("+")[:10]
                except Exception:
                    pass
            out.append((dv["id"], since))
    return out


def _wiki_incumbent(subject, role):
    """(name, since, url) from the infobox of the office's own Wikipedia article, or None.
    Editors update these within hours of a change; Wikidata's country statements can lag by years
    (it still listed a 2022 PM for Nepal in Nov 2026)."""
    query = f"{role} of {subject}"
    hits = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": 3, "format": "json"})).get("query", {}).get("search", [])
    subj_words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", subject)}
    for hit in hits:
        title = hit["title"]
        if subj_words and not subj_words & {w.lower() for w in re.findall(r"[A-Za-z]{4,}", title)}:
            continue
        wt = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "parse", "page": title, "prop": "wikitext", "section": 0, "format": "json", "formatversion": 2})
        ).get("parse", {}).get("wikitext", "")
        m = re.search(r"\|\s*(?:incumbent|current_?monarch|monarch)\s*=\s*(.+)", wt)
        if not m:
            continue
        name = _clean_wikitext(m.group(1))
        if not name:
            continue
        since = re.search(r"\|\s*(?:incumbent_?since|since|began)\s*=\s*(.+)", wt)
        return name, _clean_wikitext(since.group(1)) if since else "", "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    return None


def _clean_wikitext(v):
    v = re.sub(r"<ref.*?(</ref>|/>)", "", v, flags=re.S)
    v = re.sub(r"\{\{\s*(?:start date|start date and age)[^}]*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})[^}]*\}\}", r"\1-\2-\3", v, flags=re.I)
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\{\{.*?\}\}", "", v)
    v = re.sub(r"<[^>]+>|'{2,}", "", v)
    return v.strip(" |,")


def _same_person(a, b):
    ta = {w.lower() for w in re.findall(r"[^\W\d_]{3,}", a)}
    tb = {w.lower() for w in re.findall(r"[^\W\d_]{3,}", b)}
    return bool(ta & tb)


def officeholder(subject, role):
    """Fail closed: two sources agree -> state it; they disagree -> show both, never assert one blindly."""
    if not subject or not role:
        return None
    prop = label = None
    for rx, p, lbl in ROLE_PROPS:
        if re.search(r"\b(" + rx + r")", role, re.I):
            prop, label = p, lbl
            break
    wiki = None
    try:
        wiki = _wiki_incumbent(subject, role)
    except Exception:
        pass
    wd_lines, wd_names, wd_src = [], [], ""
    if prop:
        try:
            hits = _wd({"action": "wbsearchentities", "search": subject, "language": "en", "limit": "1"}).get("search", [])
            if hits:
                qid = hits[0]["id"]
                values = _truthy(qid, prop)
                if values:
                    ids = "|".join(v[0] for v in values[:5])
                    ents = _wd({"action": "wbgetentities", "ids": ids, "props": "labels|sitelinks", "languages": "en"})["entities"]
                    for vid, since in values[:5]:
                        e = ents.get(vid, {})
                        name = e.get("labels", {}).get("en", {}).get("value") or e.get("sitelinks", {}).get("enwiki", {}).get("title") or vid
                        wd_names.append(name)
                        wd_lines.append(name + (f" (since {since})" if since else ""))
                    wd_src = f"https://www.wikidata.org/wiki/{qid}#{prop}"
        except Exception:
            pass
    if wiki and wd_names and any(_same_person(wiki[0], n) for n in wd_names):
        since = f" (since {wiki[1]})" if wiki[1] else ""
        return f"Current {role} of {subject}: {wiki[0]}{since}. Wikipedia and Wikidata agree.\nSources: {wiki[2]} · {wd_src}"
    if wiki and wd_names:
        since = f" (since {wiki[1]})" if wiki[1] else ""
        return (f"Sources disagree on the current {role} of {subject}.\n- Wikipedia's article on the office: {wiki[0]}{since} — {wiki[2]}\n"
                f"- Wikidata: {'; '.join(wd_lines)} — {wd_src}\nWikipedia's office infobox is usually updated first, so lead with it, "
                "and say plainly that the sources disagree.")
    if wiki:
        since = f" (since {wiki[1]})" if wiki[1] else ""
        return f"Current {role} of {subject}: {wiki[0]}{since}, per Wikipedia (not cross-checked).\nSource: {wiki[2]}"
    if wd_names:
        return (f"Wikidata lists as {label} of {subject}: {'; '.join(wd_lines)}. Not cross-checked, and Wikidata can lag "
                f"by years, so say it may be out of date.\nSource: {wd_src}")
    return None


def historical(query, prompt):
    """Lines of the most relevant Wikipedia article that mention the years asked about. Evidence only: a
    past fact doesn't go stale, but the model still needs a source or it hunts around the filesystem."""
    years = re.findall(r"\b(1[0-9]{3}|20[0-9]{2})\b", prompt)
    hits = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"})).get("query", {}).get("search", [])
    if not hits:
        return None
    title = hits[0]["title"]
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA_BOT}), timeout=15).read().decode("utf-8", "replace")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    rows = re.split(r"</tr>|</li>|</p>", text)
    plain = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r)).strip() for r in rows]
    # Lifespans "(1928–2015)" and citation templates aren't what the row is about.
    plain = [re.sub(r"\s+", " ", re.sub(r"\{\{.*?\}\}|\[[^\]]*\]|\([^)]*\)", " ", l)).strip() for l in plain]
    # A row counts if it names the year, or spans it ("2014 – 2015" tables list start and end dates).
    def relevant(line):
        if not years:
            return False
        found = [int(y) for y in re.findall(r"\b(1[0-9]{3}|20[0-9]{2})\b", line)]
        return any(int(y) in found or (len(found) >= 2 and min(found) <= int(y) <= max(found)) for y in years)
    picked = [l[:260] for l in plain if relevant(l)][:14] if years else plain[:6]
    if not picked:
        return None
    return f"From Wikipedia, {title}:\n" + "\n".join(f"- {l}" for l in picked) + f"\nSource: {url}"


# ── tool versions ─────────────────────────────────────────────────────────────
# Names whose registry identity isn't the name itself. Everything else is looked up by name.
ALIASES = {
    "laravel": ("composer", "laravel/framework"), "symfony": ("composer", "symfony/symfony"),
    "livewire": ("composer", "livewire/livewire"), "filament": ("composer", "filament/filament"),
    "node": ("github", "nodejs/node"), "nodejs": ("github", "nodejs/node"), "node.js": ("github", "nodejs/node"),
    "php": ("github", "php/php-src"), "python": ("github", "python/cpython"), "cpython": ("github", "python/cpython"),
    "ruby": ("github", "ruby/ruby"), "rails": ("github", "rails/rails"), "rust": ("github", "rust-lang/rust"),
    "go": ("go", ""), "golang": ("go", ""), "docker": ("github", "moby/moby"), "kubernetes": ("github", "kubernetes/kubernetes"),
    "k8s": ("github", "kubernetes/kubernetes"), "ollama": ("github", "ollama/ollama"), "nginx": ("github", "nginx/nginx"),
    "postgres": ("github", "postgres/postgres"), "postgresql": ("github", "postgres/postgres"), "redis": ("github", "redis/redis"),
    "angular": ("npm", "@angular/core"), "tailwind": ("npm", "tailwindcss"), "tailwindcss": ("npm", "tailwindcss"),
    "next": ("npm", "next"), "nextjs": ("npm", "next"), "next.js": ("npm", "next"), "vuejs": ("npm", "vue"),
}
_PRE = re.compile(r"(dev|alpha|beta|rc\d|[-._]rc|pre|canary|nightly|snapshot)", re.I)


def _npm(name):
    d = get_json(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@/')}/latest")
    return d["version"], f"https://www.npmjs.com/package/{name}"


def _pypi(name):
    d = get_json(f"https://pypi.org/pypi/{name}/json")
    return d["info"]["version"], f"https://pypi.org/project/{name}/"


def _crates(name):
    d = get_json(f"https://crates.io/api/v1/crates/{name}")
    return d["crate"]["max_stable_version"], f"https://crates.io/crates/{name}"


def _composer(name):
    if "/" not in name:  # find the package by name
        hits = get_json("https://packagist.org/search.json?" + urllib.parse.urlencode({"q": name, "per_page": 5})).get("results", [])
        exact = [h for h in hits if h["name"].split("/")[-1] == name] or hits
        if not exact:
            raise LookupError(name)
        name = exact[0]["name"]
    d = get_json(f"https://repo.packagist.org/p2/{name}.json")
    vers = [p["version"] for p in d["packages"][name]]
    return next((v for v in vers if not _PRE.search(v)), vers[0]), f"https://packagist.org/packages/{name}"


def _stable_version(tag):
    """(numeric tuple, 'x.y.z') for a stable release tag, else None. Handles v1.2.3, php-8.5.1, REL_18_1,
    release-1.31.8, docker-v29.0.1. Rejects 3.16.0a1, REL_18_BETA1, 2.0.0-rc.1 and tags with no version."""
    m = re.search(r"(\d+)[._-](\d+)(?:[._-](\d+))?(?:[._-](\d+))?", tag)
    if not m or _PRE.search(tag):
        return None
    if re.match(r"[-._]?[a-zA-Z]+\d*", tag[m.end():]):  # 3.16.0a1, 1.2.3b2, 1.2.3-foo
        return None
    nums = tuple(int(g) for g in m.groups() if g is not None)
    return nums, ".".join(map(str, nums))


def _highest_tag(repo):
    """Highest stable tag of the repo's main tag family, compared numerically. GitHub's tag list is not in
    version order (postgres came back as release-6-3), and across all families ancient oddities win
    (PG95-1_09 "beats" REL_18_1). `git ls-remote` sees every tag and has no API rate limit."""
    out = subprocess.run(["git", "ls-remote", "--tags", "--refs", f"https://github.com/{repo}"],
                         capture_output=True, text=True, timeout=15).stdout
    families = {}
    for line in out.splitlines():
        tag = line.split("refs/tags/")[-1]
        if "/" in tag:  # monorepo sub-tags, e.g. moby's api/v1.52
            continue
        parsed = _stable_version(tag)
        if parsed:
            family = re.sub(r"[^a-z]", "", re.split(r"\d", tag, maxsplit=1)[0].lower())
            families.setdefault(family, []).append(parsed)
    if not families:
        return None
    return max(max(families.values(), key=len))[1]


def _github(repo):
    if "/" not in repo:  # most-starred repo by that name
        hits = get_json("https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": f"{repo} in:name", "sort": "stars", "per_page": 1})).get("items", [])
        if not hits:
            raise LookupError(repo)
        repo = hits[0]["full_name"]
    # A published "latest release" is the project's own statement of what's current.
    try:
        tag = get_json(f"https://api.github.com/repos/{repo}/releases/latest").get("tag_name") or ""
        parsed = _stable_version(tag)
        if parsed:
            return parsed[1], f"https://github.com/{repo}/releases/latest"
    except Exception:
        pass
    ver = _highest_tag(repo)
    if not ver:
        raise LookupError(f"no stable version tag in {repo}")
    return ver, f"https://github.com/{repo}/tags"


def _go(_):
    req = urllib.request.Request("https://go.dev/VERSION?m=text", headers={"User-Agent": UA_BROWSER})
    return urllib.request.urlopen(req, timeout=10).read().decode().splitlines()[0], "https://go.dev/dl/"


REGISTRIES = {"npm": _npm, "pypi": _pypi, "crates": _crates, "composer": _composer, "github": _github, "go": _go}


def tool_latest(tool, ecosystem="unknown"):
    if not tool:
        return None
    name = tool.strip().lower()
    if name in ALIASES:
        ecosystem, ident = ALIASES[name]
        plan = [(ecosystem, ident)]
    elif ecosystem in REGISTRIES:
        plan = [(ecosystem, name)]
    else:  # unknown ecosystem: ask every package registry that might know the name
        plan = [("npm", name), ("pypi", name), ("crates", name), ("composer", name)]
    found = []
    for eco, ident in plan:
        try:
            ver, url = REGISTRIES[eco](ident)
            found.append((eco, ver, url))
        except Exception:
            continue
    if not found:
        return None
    if len(found) == 1:
        eco, ver, url = found[0]
        return f"Latest published version of {tool}: {ver} ({eco} registry, fetched just now).\nSource: {url}"
    lines = "\n".join(f"- {eco}: {ver} — {url}" for eco, ver, url in found)
    return (f"'{tool}' exists in several registries (they may be different projects); latest published versions, "
            f"fetched just now:\n{lines}\nUse the one that matches what the user means.")
