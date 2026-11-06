#!/usr/bin/env python3
"""The parts of web access that need more than the standard library. webkit.py runs this under the web environment's Python,
so Sakura still works, more simply, on a machine that hasn't run sakura-web-setup.

  heavy.py render URL   load in headless Chromium, for pages built by JavaScript
  heavy.py extract      main text of the HTML on stdin

Prints JSON: {"status", "url", "ctype", "html"} or {"text"}, or {"error"}.
"""
import json
import sys


def render(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass  # some pages never go quiet; what's there by now is what we read
            return {"status": response.status if response else 0, "url": page.url, "ctype": "text/html", "html": page.content()}
        finally:
            browser.close()


def extract(html):
    import trafilatura
    return {"text": trafilatura.extract(html, include_links=True, include_tables=True, favor_recall=True, output_format="markdown") or ""}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "render":
            out = render(sys.argv[2])
        elif mode == "extract":
            out = extract(sys.stdin.read())
        else:
            out = {"error": "usage: heavy.py render URL, or extract"}
    except Exception as e:
        out = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
