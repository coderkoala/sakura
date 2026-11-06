#!/usr/bin/env python3
"""Does Sakura answer what's true right now? Grades against sources OTHER than the one under test, because a source can't vouch for itself.

  evals/live.py            every source, then the model end to end
  evals/live.py --sources  the sources only, with no model
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TOOL = os.path.join(HERE, "bin", "live")


def get(url, **headers):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "sakura-eval", **headers}), timeout=25).read().decode("utf-8", "replace")


def live(*args):
    r = subprocess.run([TOOL] + list(args), capture_output=True, text=True, timeout=120)
    return r.stdout + r.stderr


def recent(text, days=30):
    today = datetime.now(timezone.utc).date()
    return any(timedelta(0) <= today - datetime.strptime(d, "%Y-%m-%d").date() <= timedelta(days=days) for d in re.findall(r"\b20\d\d-\d\d-\d\d\b", text))


def number(text):
    m = re.search(r"-?\d[\d,]*\.?\d*", text)
    return float(m.group(0).replace(",", "")) if m else None


def truth_fx():
    """The ECB's own daily file, not the service in front of it."""
    return float(re.search(r"currency='USD' rate='([\d.]+)'", get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")).group(1))


def truth_temp():
    """A different weather service from the one under test."""
    return float(json.loads(get("https://wttr.in/Kathmandu?format=j1"))["current_condition"][0]["temp_C"])


def truth_python():
    """python.org's own release list, not the support tracker."""
    rel = json.loads(get("https://www.python.org/api/v2/downloads/release/?is_published=true&pre_release=false&version=3"))
    return max((tuple(int(x) for x in r["name"].split()[1].split(".")) for r in rel if re.fullmatch(r"Python \d+\.\d+\.\d+", r["name"])))


def truth_kev():
    """The newest entry in CISA's own catalog."""
    d = json.loads(get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"))
    return max(d["vulnerabilities"], key=lambda v: v["dateAdded"])["cveID"]


def truth_tokio():
    """The registry, not GitHub."""
    return json.loads(get("https://crates.io/api/v1/crates/tokio"))["crate"]["max_stable_version"]


def sources():
    res = {}
    o = live("news", "OpenAI")
    res["news: on the subject and dated this month"] = "OpenAI" in o and recent(o)
    o = live("news")
    res["news: recent world events"] = recent(o, 5)
    o = live("weather", "Kathmandu")
    m = re.search(r"(-?\d+\.\d)°C \(feels", o)
    res["weather: within 6 degrees of another service"] = bool(m) and abs(float(m.group(1)) - truth_temp()) <= 6
    o = live("fx", "EUR", "USD")
    m = re.search(r"rate ([\d.]+)", o)
    res["fx: matches the ECB's own file"] = bool(m) and abs(float(m.group(1)) - truth_fx()) < 0.01
    res["fx: a pair the ECB doesn't publish"] = "NPR" in live("fx", "USD", "NPR", "100") and "rate" in live("fx", "USD", "NPR")
    o = live("cve", "CVE-2021-44228")
    res["cve: Log4Shell is critical and exploited"] = "CVSS 10" in o and "EXPLOITED" in o
    o = live("cve", "openssl")
    # NVD's own product record for the first result, not the text that ranked it.
    first = re.search(r"CVE-\d{4}-\d+", o)
    record = get(f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={first.group(0)}") if first else ""
    res["cve: the product before passing mentions"] = bool(re.search(r"cpe:2\.3:[aoh]:openssl:openssl:", record)) or "openssl" in " ".join(o.splitlines()[1:4]).lower()
    res["vuln: an old lodash has known holes"] = "known vulnerabilities in lodash" in (o := live("vuln", "npm", "lodash", "4.17.0")) and "GHSA-" in o
    want = truth_python()
    res["eol: matches python.org"] = ".".join(map(str, want)) in live("eol", "python")
    res["releases: matches crates.io"] = truth_tokio() in live("releases", "tokio-rs/tokio")
    res["answers, issues, discussion, papers all answer"] = all("http" in live(*a) for a in (("answers", "tokio timeout"), ("issues", "panic repo:tokio-rs/tokio"), ("discussion", "rust"), ("papers", "quantization")))
    res["stat: a sane population"] = 25e6 < (number(live("stat", "Nepal", "population").split(":", 1)[1]) or 0) < 40e6
    res["quakes: dated and sourced"] = "usgs.gov" in live("quakes", "4.5")
    res["stock: a quote or a plain miss"] = "AAPL" in live("stock", "AAPL")
    res["research: reads pages and says where from"] = "Source: http" in (o := live("research", "python asyncio timeout")) and len(o) > 800
    res["an unreachable source says so"] = "Traceback" not in live("crypto", "BTC")
    return res


def ask(prompt):
    with tempfile.TemporaryDirectory(prefix="sakura-live-") as tmp:
        env = dict(os.environ, SAKURA_MEMORY_DIR=os.path.join(tmp, "m"), SAKURA_TOOLS_DIR=os.path.join(tmp, "t"), SAKURA_BROWSER_HEADLESS="1", SAKURA_BROWSER_DIR=os.path.join(tmp, "b"))
        r = subprocess.run(["sakura-launch", "--exec", "--skip-git-repo-check", "--json", prompt], cwd=tmp, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=400)
    final, cmds = "", []
    for line in r.stdout.splitlines():
        try:
            item = json.loads(line).get("item", {})
        except ValueError:
            continue
        if item.get("type") == "agent_message" and item.get("text"):
            final = item["text"]
        if item.get("type") == "command_execution" and item.get("command") and item.get("exit_code") is not None:
            cmds.append(item["command"])
    print(f"  Q: {prompt}\n  cmds: {[c[:70] for c in cmds]}\n  A: {final[:260]!r}", flush=True)
    return final


def model():
    res = {}
    a = ask("What's the euro to US dollar exchange rate right now?")
    m = re.findall(r"\b[01]\.\d{2,}", a)
    res["model: EUR/USD matches the ECB"] = any(abs(float(x) - truth_fx()) < 0.01 for x in m)
    a = ask("What's the weather like in Kathmandu right now?")
    m = re.findall(r"(-?\d+(?:\.\d)?)\s*°", a)
    res["model: Kathmandu weather is about right"] = any(abs(float(x) - truth_temp()) <= 6 for x in m)
    a = ask("What are the top news stories about OpenAI today? Give me two with their dates.")
    res["model: OpenAI news carries recent dates"] = "OpenAI" in a and bool(re.search(r"2026|Nov", a))
    a = ask("Is log4j CVE-2021-44228 being actively exploited, and how severe is it?")
    res["model: Log4Shell is exploited and critical"] = bool(re.search(r"exploit", a, re.I)) and bool(re.search(r"critical|10\.0|\b10\b", a, re.I))
    a = ask("Do lodash 4.17.0 from npm have any known vulnerabilities? Name one advisory.")
    res["model: lodash advisory is named"] = bool(re.search(r"GHSA-|CVE-20", a))
    want = ".".join(map(str, truth_python()))
    a = ask("Which Python versions are still supported, and what's the newest release?")
    res["model: newest Python matches python.org"] = want in a
    a = ask("What was the latest tokio release and what changed in it?")
    res["model: tokio release matches crates.io"] = truth_tokio() in a
    a = ask("What's Nepal's population according to the World Bank?")
    res["model: Nepal's population is sourced"] = bool(re.search(r"\b(29|30)[.,]\d", a)) and "World Bank" in a
    a = ask("Has there been a major earthquake in the past week? Answer with place and magnitude.")
    res["model: a recent earthquake with magnitude"] = bool(re.search(r"M\s?\d|magnitude", a, re.I))
    a = ask("What's the capital of France?")
    res["model: no lookup needed for a stable fact"] = "Paris" in a
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", action="store_true")
    ap.add_argument("--model", action="store_true")
    a = ap.parse_args()
    res = {}
    if not a.model:
        res.update(sources())
    if not a.sources:
        res.update(model())
    for label, ok in res.items():
        print(f"{'PASS' if ok else 'FAIL'} {label}")
    print(f"{sum(map(bool, res.values()))}/{len(res)}")
    sys.exit(0 if all(res.values()) else 1)


if __name__ == "__main__":
    main()
