#!/usr/bin/env python3
"""Sakura eval runner — measure, don't read transcripts.

Runs each case in evals/cases.json through `sakura exec --json` and grades it from the event
stream (final answer, executed commands, tokens, wall time) plus on-disk checks. Expected
answers for current facts and versions are fetched LIVE from authoritative sources here,
independently of Sakura's own lookup code, so a bug there can't grade itself as correct.

  python3 evals/run.py                 # all cases, model routed like `?`
  python3 evals/run.py --tag version   # one tag
  python3 evals/run.py --only fact-nepal-pm,code-fix-bug
  python3 evals/run.py --model huihui_ai/qwen3.5-abliterated:9b   # force a model
  python3 evals/run.py --list

Results: evals/results/<timestamp>.json (gitignored) and a summary table on stdout.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.realpath(__file__))
SAKURA = os.environ.get("SAKURA_BIN", os.path.expanduser("~/.local/bin/sakura"))
ROUTER = os.path.join(HERE, "..", "..", "bash", "86-sakura.sh")  # dotfiles/bash, when vendored as dotfiles/sakura
DEFAULT_MODEL = "huihui_ai/qwen3.5-abliterated:9b"
UA = "sakura-evals/0.1 (local eval harness)"


# ── live ground truth ─────────────────────────────────────────────────────────
_CACHE_PATH = os.path.join(HERE, "results", ".ground-truth-cache.json")
try:
    _CACHE = {k: v for k, v in json.load(open(_CACHE_PATH)).items() if time.time() - v[0] < 86400}
except Exception:
    _CACHE = {}


def _get(url, timeout=20, headers=None):
    """GET with retry/backoff on 429/5xx and a 24h disk cache, so repeated runs don't hammer the
    authoritative sources (Wikimedia rate-limits this host during its outages)."""
    if url in _CACHE:
        return _CACHE[url][1]
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
            _CACHE[url] = (time.time(), body)
            try:
                os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
                json.dump(_CACHE, open(_CACHE_PATH, "w"))
            except Exception:
                pass
            return body
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(min(8, int(e.headers.get("Retry-After") or 0) or 2 ** (attempt + 1)))
    raise last


def _wd_api(params):
    return json.loads(_get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})))


def wikidata_truthy(entity, prop):
    """Labels of the truthy values of entity/prop: Wikidata's own definition — the preferred-rank
    statements if any exist, else the normal-rank ones (deprecated never). Same semantics as SPARQL
    `wdt:`; done via the Action API because the query service throttles to 1 req/min during outages."""
    claims = _wd_api({"action": "wbgetentities", "ids": entity, "props": "claims"})["entities"][entity]["claims"].get(prop, [])
    preferred = [c for c in claims if c.get("rank") == "preferred"]
    best = preferred or [c for c in claims if c.get("rank") == "normal"]
    ids = [c["mainsnak"]["datavalue"]["value"]["id"] for c in best if c["mainsnak"].get("datavalue")]
    if not ids:
        return []
    ents = _wd_api({"action": "wbgetentities", "ids": "|".join(ids[:50]), "props": "labels", "languages": "en"})["entities"]
    return [ents[i]["labels"].get("en", {}).get("value", i) for i in ids]


def registry_latest(kind, name):
    if kind == "packagist":
        d = json.loads(_get(f"https://repo.packagist.org/p2/{name}.json"))
        vers = [p["version"] for p in d["packages"][name]]
        return next(v for v in vers if not re.search(r"dev|alpha|beta|rc", v, re.I))
    if kind == "npm":
        return json.loads(_get(f"https://registry.npmjs.org/{name}/latest"))["version"]
    if kind == "pypi":
        return json.loads(_get(f"https://pypi.org/pypi/{name}/json"))["info"]["version"]
    raise ValueError(kind)


def feed_titles(url):
    root = ET.fromstring(_get(url, headers={"Accept": "application/xml"}))
    return [e.text.strip() for e in root.iter() if e.tag.split("}")[-1] == "title" and e.text][1:]


def resolve_expectation(e):
    """Turn a 'live' expectation into concrete acceptable strings. Returns (label, [patterns])."""
    live = e.get("live")
    if live == "wikidata":
        labels = wikidata_truthy(e["entity"], e["prop"])
        pats = []
        for lab in labels:
            toks = [t for t in re.split(r"[\s,]+", lab) if len(t) >= 4 and not re.fullmatch(r"[IVX]+", t)]
            pats.append(re.escape(toks[-1] if toks else lab))
        return f"wikidata {e['entity']}/{e['prop']} = {labels}", pats
    if live in ("packagist", "npm", "pypi"):
        v = registry_latest(live, e["name"]).lstrip("vV")
        parts = v.split(".")
        want = {"major": parts[0], "minor": ".".join(parts[:2]), "exact": v}[e.get("match", "minor")]
        # 'major' must not match inside a larger number (13 vs 130 / 2013)
        return f"{live} {e['name']} = {v}", [r"(?<![\d.])v?" + re.escape(want) + r"(?![\d])"]
    if live == "feed_titles":
        titles = feed_titles(e["url"])
        return f"feed titles ({len(titles)})", [re.escape(t[:40]) for t in titles]
    if "regex" in e:
        return f"regex {e['regex']}", [e["regex"]]
    raise ValueError(f"unknown expectation {e}")


# ── running a case ────────────────────────────────────────────────────────────
def route_model(prompt):
    if os.path.exists(ROUTER):
        try:
            out = subprocess.run(["bash", "-c", f'source "{ROUTER}" >/dev/null 2>&1; _sakura_pick_model "$1"', "_", prompt],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
            if out:
                return out
        except Exception:
            pass
    return DEFAULT_MODEL


def run_case(case, model_override, timeout):
    work = tempfile.mkdtemp(prefix=f"sakura-eval-{case['id']}-")
    cwd = os.path.expanduser(case.get("cwd", "~").replace("{work}", work))
    prompt = case["prompt"].replace("{work}", work)
    if case.get("setup"):
        subprocess.run(["bash", "-c", case["setup"]], cwd=cwd, check=True)
    model = model_override or route_model(prompt)
    # Not --ephemeral: the Stop verifier reads the turn's transcript, so evals must exercise the real path.
    cmd = [SAKURA, "exec", "--dangerously-bypass-hook-trust", "--skip-git-repo-check", "--json",
           "-m", model, prompt]
    t0 = time.time()
    timed_out = False
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        stdout = p.stdout
    except subprocess.TimeoutExpired as ex:
        timed_out = True
        stdout = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or "")
    secs = time.time() - t0

    answer_parts, commands, tokens_in, tokens_out = [], [], 0, 0
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        item = ev.get("item", {})
        if ev.get("type") == "item.completed" and item.get("type") == "agent_message" and item.get("text"):
            answer_parts.append(item["text"])
        if ev.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands.append(item.get("command", ""))
        if ev.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
            commands.append(f"mcp:{item.get('server')}.{item.get('tool')} {json.dumps(item.get('arguments'))}")
        if ev.get("type") == "turn.completed":
            u = ev.get("usage", {})
            tokens_in += u.get("input_tokens", 0)
            tokens_out += u.get("output_tokens", 0)
    # Grade the final answer the user sees — not drafts the Stop verifier sent back.
    answer = answer_parts[-1] if answer_parts else ""

    checks = []
    if timed_out:
        checks.append(("finished", False, f"timed out after {timeout}s"))
    for e in case.get("expect", []):
        try:
            label, pats = resolve_expectation(e)
        except Exception as ex:
            checks.append(("expect", None, f"ground truth unavailable: {ex}"))
            continue
        ok = any(re.search(p, answer, re.I) for p in pats)
        checks.append(("expect", ok, label))
    for f in case.get("forbid", []):
        hit = re.search(f["regex"], answer)
        checks.append(("forbid", not hit, f"answer must not match {f['regex']}" + (f" (got: {hit.group(0)!r})" if hit else "")))
    for f in case.get("forbid_cmd", []):
        bad = [c for c in commands if re.search(f["regex"], c)]
        checks.append(("forbid_cmd", not bad, f"no command matching {f['regex']}" + (f" (ran: {bad[0][:80]!r})" if bad else "")))
    if case.get("check"):
        r = subprocess.run(["bash", "-c", case["check"]], cwd=cwd, capture_output=True, text=True)
        checks.append(("on_disk", r.returncode == 0, case["check"][:70]))
    if case.get("max_seconds"):
        checks.append(("speed", secs <= case["max_seconds"], f"{secs:.0f}s <= {case['max_seconds']}s"))

    graded = [c for c in checks if c[1] is not None]
    # No gradable check (ground truth unavailable) → skipped, not failed: don't score the grader's outage.
    passed = None if not graded else all(c[1] for c in graded)
    shutil.rmtree(work, ignore_errors=True)
    return {"id": case["id"], "tags": case.get("tags", []), "model": model, "passed": passed,
            "seconds": round(secs, 1), "tokens_in": tokens_in, "tokens_out": tokens_out,
            "commands": commands, "answer": answer[-1500:], "drafts": len(answer_parts),
            "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    ap.add_argument("--only")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--label", default="", help="free-text label stored with the results (e.g. 'baseline')")
    a = ap.parse_args()

    cases = json.load(open(os.path.join(HERE, "cases.json")))["cases"]
    if a.tag:
        cases = [c for c in cases if a.tag in c.get("tags", [])]
    if a.only:
        want = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in want]
    if a.list:
        for c in cases:
            print(f"{c['id']:28s} {','.join(c.get('tags', []))}")
        return

    results = []
    for i, c in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {c['id']} …", end="", flush=True)
        r = run_case(c, a.model, a.timeout)
        results.append(r)
        mark = {True: "PASS", False: "FAIL", None: "SKIP"}[r["passed"]]
        print(f" {mark}  {r['seconds']:>5.0f}s  {r['tokens_in']:>7} tok  {r['model'].split(':')[-1]}")
        for ch in r["checks"]:
            if ch["ok"] is not True:
                print(f"        {'✗' if ch['ok'] is False else '?'} {ch['name']}: {ch['detail']}")

    scored = [r for r in results if r["passed"] is not None]
    n = len(scored)
    p = sum(1 for r in scored if r["passed"])
    skipped = len(results) - n
    print(f"\nSCORE {p}/{n}  ({100 * p // max(n, 1)}%)" + (f"   ({skipped} skipped: ground truth unavailable)" if skipped else ""))
    tags = sorted({t for r in scored for t in r["tags"]})
    for t in tags:
        rs = [r for r in scored if t in r["tags"]]
        print(f"  {t:12s} {sum(1 for r in rs if r['passed'])}/{len(rs)}")
    m = len(results)
    tot_s = sum(r["seconds"] for r in results)
    print(f"  time {tot_s:.0f}s total, median {sorted(r['seconds'] for r in results)[m // 2]:.0f}s; "
          f"median input tokens {sorted(r['tokens_in'] for r in results)[m // 2]}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = os.path.join(HERE, "results", time.strftime("%Y%m%d-%H%M%S") + (f"-{a.label}" if a.label else "") + ".json")
    json.dump({"label": a.label, "score": [p, n], "results": results}, open(out, "w"), indent=1)
    print(f"  saved {out}")
    sys.exit(0 if p == n else 1)


if __name__ == "__main__":
    main()
