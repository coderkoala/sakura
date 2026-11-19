#!/usr/bin/env python3
"""The user's own Firefox as Sakura's browser: the same program, profile, cookies and logins as the person at the keyboard.

Firefox listens for WebDriver BiDi on 127.0.0.1 only when it was started with --remote-debugging-port, so
`sakura-browser share on` gives its launcher that flag (and `share off` takes it away). Sakura then opens one window of
its own in that Firefox and works only in the tabs it opened, and the ones those open; the user's own tabs are never
read or touched. The class here offers the handful of page calls browserd makes on a Playwright page, so the human-check,
login and password rules in browserd apply unchanged.

The cost, measured on Firefox 154: while it listens, Firefox reports navigator.webdriver = true on every page, the user's
own browsing included, so some sites will show more checks or refuse a sign-in. Nothing here hides that.
"""
import base64
import configparser
import json
import os
import shlex
import socket
import subprocess
import time

PORT = int(os.environ.get("SAKURA_FIREFOX_PORT") or 9222)
MARK = "# sakura-browser share on:"
FAMILY = ("firefox", "librewolf", "waterfox", "floorp", "org.mozilla")
ENTER, BACKSPACE = "", ""
KEYS = {"Enter": ENTER, "Tab": "", "Escape": "", "Backspace": BACKSPACE}
RETRY = ("no such frame", "destroyed", "navigat", "no such node", "discarded")


class NotShared(Exception):
    pass


# --- which browser, and its launcher -------------------------------------------------------------------------------

def default_desktop_id():
    if os.environ.get("BROWSER"):
        return os.path.basename(os.environ["BROWSER"].split(":")[0].split()[0])
    try:
        return subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def default_is_firefox():
    return any(f in default_desktop_id().lower() for f in FAMILY)


def user_apps():
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "applications")


def system_desktop_file(did):
    """The launcher the system ships for this browser, never our own override."""
    dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") + ["/var/lib/snapd/desktop", "/var/lib/flatpak/exports/share"]
    for d in dirs:
        p = os.path.join(d, "applications", did)
        if os.path.isfile(p):
            return p
    return None


def override_path(did=None):
    return os.path.join(user_apps(), did or default_desktop_id() or "firefox.desktop")


def with_flag(exec_line, port):
    """An Exec= value with --remote-debugging-port added after the program (and after a flatpak app id)."""
    if "--remote-debugging-port" in exec_line:
        return exec_line
    toks = shlex.split(exec_line)
    at = None
    for i, t in enumerate(toks):
        base = os.path.basename(t)
        if base in ("firefox", "firefox-esr", "librewolf", "waterfox", "floorp") or t.startswith("org.mozilla."):
            at = i + 1
    if at is None:
        at = next((i for i, t in enumerate(toks) if t.startswith("%")), len(toks))
    toks[at:at] = ["--remote-debugging-port", str(port)]
    return shlex.join(toks).replace("'%u'", "%u").replace("'%U'", "%U")


def share_on(port=PORT):
    did = default_desktop_id()
    if not any(f in did.lower() for f in FAMILY):
        return 1, f"the default browser is {did or 'not set'}, not Firefox; sharing works with Firefox only"
    src = system_desktop_file(did)
    if not src:
        return 1, f"no launcher {did} found to copy"
    out = [f"{MARK} Firefox's launcher with WebDriver BiDi on 127.0.0.1:{port}, so Sakura can use this Firefox. Undo: sakura-browser share off"]
    for line in open(src, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("Exec="):
            line = "Exec=" + with_flag(line[5:], port)
        out.append(line)
    os.makedirs(user_apps(), exist_ok=True)
    with open(override_path(did), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    subprocess.run(["update-desktop-database", user_apps()], capture_output=True)
    return 0, (f"sharing on: {override_path(did)} starts Firefox listening on 127.0.0.1:{port}.\n"
               + ("Firefox is open now: quit it and open it again for this to take effect.\n" if firefox_running() and not port_open(port) else "")
               + "While it listens, every site sees navigator.webdriver = true, so some will show more checks. sakura-browser share off undoes it.")


def share_off():
    p = override_path()
    if os.path.isfile(p) and open(p, encoding="utf-8").readline().startswith(MARK):
        os.unlink(p)
        subprocess.run(["update-desktop-database", user_apps()], capture_output=True)
        return 0, "sharing off: Firefox's own launcher is back. Quit Firefox and open it again to stop it listening."
    return 0, "sharing was already off"


def share_status(port=PORT):
    p = override_path()
    on = os.path.isfile(p) and open(p, encoding="utf-8").readline().startswith(MARK)
    return 0, "\n".join([
        f"default browser: {default_desktop_id() or 'not set'}",
        f"launcher: {'shares (' + p + ')' if on else 'Firefox own (sharing off)'}",
        f"Firefox: {'running' if firefox_running() else 'not running'}, {'listening on 127.0.0.1:%d' % port if port_open(port) else 'not listening'}",
    ])


def firefox_running():
    return subprocess.run(["pgrep", "-x", "firefox|firefox-bin|firefox-esr|librewolf"], capture_output=True).returncode == 0


def port_open(port=PORT):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def launch_command(port):
    """How to start this machine's Firefox with the flag, from its launcher (snap, flatpak and deb differ)."""
    did = default_desktop_id() or "firefox.desktop"
    for p in (override_path(did), system_desktop_file(did)):
        if p and os.path.isfile(p):
            cp = configparser.RawConfigParser(strict=False, interpolation=None)
            try:
                cp.read(p, encoding="utf-8")
                ex = cp.get("Desktop Entry", "Exec")
            except Exception:
                continue
            return [t for t in shlex.split(with_flag(ex, port)) if not (t.startswith("%") or t in ("@@u", "@@"))]
    return ["firefox", "--remote-debugging-port", str(port)]


def start_firefox(port):
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise NotShared("Firefox isn't running and there's no screen here to open it on. Ask the user to open Firefox.")
    cmd = launch_command(port)
    # Through the user's systemd, so Firefox belongs to the session and not to this daemon's process group.
    if subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--"] + cmd, capture_output=True).returncode != 0:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    end = time.time() + 45
    while time.time() < end:
        if port_open(port):
            return
        time.sleep(0.5)
    raise NotShared("Firefox started but isn't listening for Sakura. Ask the user to check `sakura-browser share status`.")


# --- the protocol --------------------------------------------------------------------------------------------------

class Bidi:
    def __init__(self, port):
        from websockets.sync.client import connect  # in the web environment (sakura-web-setup)
        self.ws = connect(f"ws://127.0.0.1:{port}/session", max_size=128 * 2**20, open_timeout=10)
        self.n = 0

    def call(self, method, params=None, timeout=35):
        from websockets.exceptions import ConnectionClosed
        self.n += 1
        mid = self.n
        try:
            self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            end = time.time() + timeout
            while True:
                left = end - time.time()
                if left <= 0:
                    raise TimeoutError(f"Firefox didn't answer {method} within {timeout}s")
                msg = json.loads(self.ws.recv(timeout=left))
                if msg.get("id") != mid:
                    continue  # events; nothing here subscribes, but don't trip on them
                if msg.get("type") == "error":
                    raise RuntimeError(f"{msg.get('error')}: {msg.get('message', '')}"[:300])
                return msg.get("result", {})
        except ConnectionClosed:
            raise RuntimeError("Firefox closed the connection") from None

    def close(self):
        try:
            self.call("session.end", timeout=5)
        except Exception:
            pass
        try:
            self.ws.close()
        except Exception:
            pass


class Firefox:
    """Stands in for a Playwright BrowserContext: .pages, .new_page(), .close()."""

    # Firefox gives each session new context ids, so a window can't be found again by a later session: browserd keeps
    # one session for as long as Firefox runs (no idle exit), and close() closes Sakura's own window.
    def __init__(self, bidi):
        self.bidi = bidi
        self.mine = []

    @classmethod
    def attach(cls):
        if not port_open(PORT):
            if firefox_running():
                raise NotShared("the user's Firefox is open without sharing on, so Sakura can't use it. Tell them: quit Firefox "
                                "and open it again (sakura-browser share on makes its launcher allow this), then try again.")
            start_firefox(PORT)
        bidi = Bidi(PORT)
        caps = {"alwaysMatch": {"unhandledPromptBehavior": {"default": "ignore"}}}  # the user's own dialogs stay theirs
        try:
            bidi.call("session.new", {"capabilities": caps})
        except RuntimeError as e:
            if "session not created" in str(e) and "prompt" in str(e).lower():
                bidi.call("session.new", {"capabilities": {}})
            elif "session not created" in str(e):
                bidi.ws.close()
                raise NotShared("something else is already driving the user's Firefox (one automation session at a time). "
                                "Run sakura-browser close, or ask the user what's using it.") from None
            else:
                raise
        return cls(bidi)

    def tree(self):
        return self.bidi.call("browsingContext.getTree", {"maxDepth": 0}).get("contexts", [])

    @property
    def pages(self):
        live = self.tree()
        ids = {c["context"] for c in live}
        for c in live:  # a tab one of ours opened (target=_blank, window.open) is ours too
            if c.get("originalOpener") in self.mine and c["context"] not in self.mine:
                self.mine.append(c["context"])
        self.mine = [m for m in self.mine if m in ids]
        return [Page(self, m) for m in self.mine]

    def new_page(self):
        # The first page gets a window of its own, so the user's tab strip stays theirs; later ones are tabs in it.
        params = {"type": "tab", "referenceContext": self.mine[0]} if self.mine else {"type": "window"}
        cid = self.bidi.call("browsingContext.create", params)["context"]
        self.mine.append(cid)
        return Page(self, cid)

    def close(self):
        """Close Sakura's own tabs (its window goes with them) and end the session. The user's tabs stay as they are."""
        for m in reversed(self.mine):
            try:
                self.bidi.call("browsingContext.close", {"context": m}, timeout=5)
            except Exception:
                pass
        self.bidi.close()


class Page:
    def __init__(self, fx, cid):
        self.fx, self.id = fx, cid

    def call(self, method, params, timeout=35):
        return self.fx.bidi.call(method, dict(params, context=self.id), timeout=timeout)

    def run(self, fn, *args, own=False):
        """Run a JS function in the page with JSON-able arguments; return its JSON-able result."""
        decl = f"(s) => Promise.resolve(({fn})(...JSON.parse(s))).then(v => JSON.stringify(v === undefined ? null : v))"
        params = {"functionDeclaration": decl, "arguments": [{"type": "string", "value": json.dumps(list(args))}],
                  "target": {"context": self.id}, "awaitPromise": True}
        for attempt in range(8):
            try:
                r = self.fx.bidi.call("script.callFunction", params)
            except RuntimeError as e:
                if attempt < 7 and any(w in str(e).lower() for w in RETRY):
                    time.sleep(0.4)  # the page is between documents
                    continue
                raise
            if r.get("type") == "exception":
                raise RuntimeError("page script failed: " + r.get("exceptionDetails", {}).get("text", "")[:200])
            return json.loads(r["result"]["value"])

    def node(self, sel):
        params = {"functionDeclaration": "(s) => document.querySelector(s)", "arguments": [{"type": "string", "value": sel}],
                  "target": {"context": self.id}, "awaitPromise": False, "resultOwnership": "root",
                  "serializationOptions": {"maxDomDepth": 0}}
        r = self.fx.bidi.call("script.callFunction", params)
        res = r.get("result", {})
        if res.get("type") != "node" or not res.get("sharedId"):
            raise RuntimeError(f"no element matches {sel}")
        return res["sharedId"]

    def act(self, *sources):
        self.call("input.performActions", {"actions": list(sources)})
        self.call("input.releaseActions", {})

    def keys(self, text):
        acts = []
        for ch in text:
            acts += [{"type": "keyDown", "value": ch}, {"type": "keyUp", "value": ch}]
        self.act({"type": "key", "id": "kbd", "actions": acts})

    # what browserd calls on a Playwright page
    @property
    def url(self):
        for c in self.fx.bidi.call("browsingContext.getTree", {"root": self.id, "maxDepth": 0}).get("contexts", []):
            return c.get("url", "")
        return ""

    def title(self):
        return self.run("() => document.title")

    def evaluate(self, fn, arg=None):
        return self.run(fn) if arg is None else self.run(fn, arg)

    def content(self):
        return self.run("() => document.documentElement ? document.documentElement.outerHTML : ''")

    def inner_text(self, sel):
        return self.run("(s) => { const e = document.querySelector(s); return e ? e.innerText : ''; }", sel)

    def goto(self, url, wait_until=None, timeout=30000):
        self.call("browsingContext.navigate", {"url": url, "wait": "interactive"}, timeout=timeout / 1000 + 5)

    def wait_for_load_state(self, state=None, timeout=5000):
        """Loaded, then no new resources for half a second: close enough to Playwright's networkidle."""
        end, last, quiet = time.time() + timeout / 1000, -1, 0.0
        while time.time() < end:
            try:
                ready, n = self.run("() => [document.readyState, performance.getEntriesByType('resource').length]")
            except Exception:
                ready, n = "loading", -1
            if ready == "complete" and n == last:
                quiet += 0.25
                if quiet >= 0.5:
                    return
            else:
                quiet, last = 0.0, n
            time.sleep(0.25)

    def wait_for_timeout(self, ms):
        time.sleep(ms / 1000)

    def go_back(self, timeout=15000):
        self.call("browsingContext.traverseHistory", {"delta": -1}, timeout=timeout / 1000 + 5)
        self.wait_for_load_state(timeout=timeout)

    def screenshot(self, path):
        data = self.call("browsingContext.captureScreenshot", {})["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))

    def bring_to_front(self):
        self.call("browsingContext.activate", {})

    def locator(self, sel):
        return Locator(self, sel)


class Locator:
    def __init__(self, page, sel):
        self.page, self.sel = page, sel

    def count(self):
        return self.page.run("(s) => document.querySelectorAll(s).length", self.sel)

    def evaluate(self, fn):
        return self.page.run(f"(s) => ({fn})(document.querySelector(s))", self.sel)

    def click(self, timeout=8000):
        """A real click (trusted events, like a person's), at the element's centre."""
        self.page.run("(s) => document.querySelector(s).scrollIntoView({block: 'center', inline: 'center'})", self.sel)
        sid = self.page.node(self.sel)
        self.page.act({"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
            {"type": "pointerMove", "x": 0, "y": 0, "origin": {"type": "element", "element": {"sharedId": sid}}},
            {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]})

    def fill(self, text, timeout=8000):
        """Replace what's in the field with text, typed as key presses so the page's own handlers see them."""
        had = self.page.run("""(s) => { const e = document.querySelector(s); e.scrollIntoView({block: 'center'}); e.focus();
            if (e.select) { e.select(); return !!e.value; }
            if (e.isContentEditable) { const r = document.createRange(); r.selectNodeContents(e);
              const g = getSelection(); g.removeAllRanges(); g.addRange(r); return !!e.textContent; }
            return false; }""", self.sel)
        self.page.keys((BACKSPACE if had else "") + text)

    def press(self, key):
        self.page.keys(KEYS.get(key, key))
