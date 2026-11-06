#!/usr/bin/env python3
"""Does web access do its job, and take no for an answer? Runs fetch_url and web_search against a local test site, with no model."""
import http.server
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
BIRDS = ["heron", "egret", "stork", "ibis", "crane", "bittern", "spoonbill", "kingfisher", "cormorant", "pelican", "osprey", "avocet"]
ARTICLE = "".join(f"<p>The {b} is a wading or fishing bird, and watching a {b} at the water's edge shows how patient it can be: it stands, waits for a long time, and strikes only when a fish comes close enough, which is why the {b} has been studied for so many years.</p>" for b in BIRDS)
SHORT = "<p>Our office is in Pokhara, near the lake, and we answer letters within a week. Write to us with the form below and tell us what you need, and someone from the team will reply to you.</p>" * 2
PAGES = {
    "/article": (200, f"<!doctype html><html><head><title>Herons</title></head><body><nav><a href='/'>MENU-NOISE</a></nav><main><article><h1>Herons</h1>{ARTICLE}</article></main></body></html>"),
    "/js": (200, "<title>App</title><div id=r></div><script>document.getElementById('r').innerHTML='" + ("<p>BUILT-BY-JS and quite a lot of readable words follow here.</p>" * 12) + "'</script>"),
    "/refused": (403, "<title>Forbidden</title>nope"),
    "/challenge": (200, "<title>Just a moment...</title><script src='https://challenges.cloudflare.com/x.js'></script>"),
    "/form": (200, f"<title>Contact</title><article>{SHORT}<p>A second paragraph says that the post also reaches us, slowly.</p></article><div class='g-recaptcha'></div>"),
    "/gone": (404, "gone"),
    "/feed.xml": (200, "<?xml version='1.0'?><rss version='2.0'><channel><title>News</title><item><title>FEED-ITEM</title></item></channel></rss>"),
}
hits = {}


class Site(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        hits[self.path] = hits.get(self.path, 0) + 1
        code, body = PAGES.get(self.path, (404, ""))
        self.send_response(code)
        self.send_header("Content-Type", "application/rss+xml" if self.path.endswith(".xml") else "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_):
        pass


def tool(name, *args):
    r = subprocess.run([os.path.join(HERE, "bin", name)] + list(args), capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def main():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    res = {}
    c, o = tool("fetch_url", base + "/article")
    res["an article reads as its main text"] = c == 0 and "The heron is a wading" in o and "MENU-NOISE" not in o
    c, o = tool("fetch_url", base + "/js")
    res["a page built by JavaScript is read"] = c == 0 and "BUILT-BY-JS" in o
    c, o = tool("fetch_url", base + "/refused")
    res["a refusal is reported, not a crash"] = c == 0 and "refused automated reading" in o and "sakura-browser open" in o
    res["a refusal is asked once, never retried"] = hits.get("/refused") == 1
    c, o = tool("fetch_url", base + "/challenge")
    res["a challenge page is reported as one"] = c == 0 and "refused automated reading" in o
    res["a challenge is asked once, never retried"] = hits.get("/challenge") == 1
    c, o = tool("fetch_url", base + "/form")
    res["a captcha widget on a real page isn't a refusal"] = c == 0 and "Pokhara" in o and "refused" not in o
    c, o = tool("fetch_url", base + "/gone")
    res["a missing page is still an error"] = c != 0 and "404" in o
    c, o = tool("fetch_url", base + "/feed.xml")
    res["a feed still renders"] = c == 0 and "FEED-ITEM" in o
    c, o = tool("web_search", "tokio rust async runtime documentation", "5")
    res["search returns web results"] = c == 0 and "Other web results:" in o and "http" in o
    for label, ok in res.items():
        print(f"{'PASS' if ok else 'FAIL'} {label}")
    print(f"{sum(map(bool, res.values()))}/{len(res)}")
    sys.exit(0 if all(res.values()) else 1)


if __name__ == "__main__":
    main()
