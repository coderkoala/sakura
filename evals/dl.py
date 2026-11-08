#!/usr/bin/env python3
"""Does dl download, stop, RESUME from the byte it stopped at, and verify? Graded by a local range-serving HTTP server
that records every Range header, by the file's bytes, and by sha256 — never by what dl prints.

  evals/dl.py
No model, no network beyond 127.0.0.1.
"""
import hashlib
import http.server
import json
import os
import re
import socketserver
import subprocess
import tempfile
import threading
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
PAYLOAD = os.urandom(1024) * 2048  # 2 MiB of incompressible bytes
RANGES = []


class RangeHandler(http.server.BaseHTTPRequestHandler):
    throttle = False

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        start = 0
        if rng:
            RANGES.append(rng)
            m = re.match(r"bytes=(\d+)-", rng)
            start = int(m.group(1)) if m else 0
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            self.send_response(200)
        body = PAYLOAD[start:]
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        try:
            chunk = 65536
            for i in range(0, len(body), chunk):
                self.wfile.write(body[i:i + chunk])
                if RangeHandler.throttle:
                    time.sleep(0.05)  # slow enough to stop mid-flight
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *a):
        pass


def run(args, env, timeout=120):
    return subprocess.run([os.path.join(BIN, "dl"), *args], env=dict(os.environ, **env), capture_output=True, text=True, timeout=timeout)


def wait_for(cond, seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.3)
    return False


def main():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), RangeHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/blob.bin"
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        env = {"SAKURA_DL_DIR": os.path.join(tmp, "state"), "SAKURA_DL_DOWNLOADS": os.path.join(tmp, "dl"), "SAKURA_PA_NOTIFY": "/bin/true"}
        qpath = os.path.join(tmp, "state", "queue.json")

        def items():
            try:
                return json.load(open(qpath))["items"]
            except (OSError, ValueError):
                return []

        # 1. stop mid-flight, then resume: the second request must be a Range from the part's size
        RangeHandler.throttle = True
        out = run(["--sha256", sha, url], env).stdout
        did = out.split()[0] if out.strip() else ""
        results["add prints an id and the size"] = bool(did) and "2.0 GB" not in out and "MB" in out
        part = os.path.join(tmp, "dl", "blob.bin.part")
        ok_grew = wait_for(lambda: os.path.exists(part) and os.path.getsize(part) > 100000, 30)
        run(["stop", did], env)
        time.sleep(0.8)
        size_at_stop = os.path.getsize(part) if os.path.exists(part) else 0
        results["stop leaves a part file with bytes"] = ok_grew and 0 < size_at_stop < len(PAYLOAD)
        time.sleep(0.5)
        size2 = os.path.getsize(part) if os.path.exists(part) else 0
        results["stopped means stopped (no growth)"] = size2 <= size_at_stop + 65536 * 2
        RANGES.clear()
        RangeHandler.throttle = False
        run(["resume", did], env)
        final = os.path.join(tmp, "dl", "blob.bin")
        results["resume finishes the file"] = wait_for(lambda: any(i.get("state") == "done" for i in items()), 90) and os.path.exists(final)
        results["the resume used a byte range, not a restart"] = any(r.startswith("bytes=") and not r.startswith("bytes=0-") for r in RANGES)
        results["the bytes are exactly right"] = os.path.exists(final) and hashlib.sha256(open(final, "rb").read()).hexdigest() == sha
        results["the checksum verdict is recorded"] = any(i.get("checksum") == "ok" for i in items())
        done_out = run(["done"], env).stdout
        results["done lists it with the path"] = "blob.bin" in done_out and "checksum ok" in done_out

        # 2. a wrong checksum is caught
        RANGES.clear()
        bad = run(["--sha256", "0" * 64, "--name", "bad.bin", url], env).stdout
        bid = bad.split()[0] if bad.strip() else ""
        results["a wrong sha256 marks it bad, file not finalized"] = (
            wait_for(lambda: any(i.get("state") == "bad-checksum" for i in items()), 90)
            and not os.path.exists(os.path.join(tmp, "dl", "bad.bin")))

        # 3. list and rm
        lst = run(["list"], env).stdout
        results["list shows both"] = "blob.bin" in lst and "bad.bin" in lst
        run(["rm", bid, "--data"], env)
        results["rm forgets it"] = "bad.bin" not in run(["list"], env).stdout
        results["a non-http link is refused"] = "not an http(s) link" in run(["magnet:?xt=x"], env).stdout
    passed = sum(bool(v) for v in results.values())
    for k, v in results.items():
        print(f"  {'ok  ' if v else 'FAIL'} {k}")
    print(f"\ndl: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
