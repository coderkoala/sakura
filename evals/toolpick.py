#!/usr/bin/env python3
"""Does Sakura reach for its own toolkit from a plain sentence, with no `?key` to point at it? Each case plants real files,
asks in ordinary words, and is graded by WHICH COMMANDS RAN (from the engine's JSON events), never by the answer's wording:
the right tool must have run, and the thing it replaces (du, ss, a website, hand-rolled ffmpeg) must not.

  evals/toolpick.py                 every case
  evals/toolpick.py --only NAME
  evals/toolpick.py --list
Needs the driver (sakura-launch brings it up). Each case gets its own memory, HOME-independent planted files, and a fake ssh
for the fleet case. Results land in evals/results/toolpick-*.json like run.py's.
"""
import argparse
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
BIN = os.path.join(ROOT, "bin")
LAUNCH = os.path.join(BIN, "sakura-launch")
ONLINE = r"ilovepdf|smallpdf|pdf2go|cloudconvert|zamzar|online-?convert|ezgif|convertio|freeconvert|adobe\.com/acrobat/online|y2mate|savefrom"


def pdf(path, text):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path)
    c.drawString(72, 700, text)
    c.showPage()
    c.save()


def clip(path):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path], check=True)


def photo(path, exif=True):
    from PIL import Image
    im = Image.new("RGB", (120, 90), "teal")
    if exif:
        ex = im.getexif()
        ex[0x010F] = "Cam"
        ex[0x0132] = "2019:07:14 10:00:00"
        im.save(path, exif=ex.tobytes())
    else:
        im.save(path)


# name: (setup(d, env) -> prompt, expected command regexes (all must have run), forbidden regexes (none may have run))
def case_space(d, env):
    return "what's eating my disk? don't delete anything yet", [r"(^|/| )space\b"], [r"(^|[;&|]\s*)(sudo\s+)?du\b", r"\bncdu\b"]


def case_ports(d, env):
    return "what's listening on this machine and which process holds each port?", [r"(^|/| )ports\b"], [r"\b(ss|lsof|netstat)\b\s+-"]


def case_when(d, env):
    return 'when does this cron line run next: "0 3 * * 1"?', [r"(^|/| )when\b"], [r"\bcrontab\b"]


def case_merge(d, env):
    pdf(os.path.join(d, "a.pdf"), "a")
    pdf(os.path.join(d, "b.pdf"), "b")
    return "merge a.pdf and b.pdf into one pdf", [r"(^|/| )conv\s+merge\b"], [ONLINE]


def case_docx(d, env):
    open(os.path.join(d, "notes.md"), "w").write("# Notes\n\nhello\n")
    return "turn notes.md into a Word document", [r"(^|/| )conv\s+\S*notes\.md\s+--to\s+docx"], [ONLINE]


def case_redact(d, env):
    pdf(os.path.join(d, "letter.pdf"), "Call me on 9841-000000 any time.")
    return "remove the phone number 9841-000000 from letter.pdf before I send it", [r"(^|/| )conv\s+redact\b"], [ONLINE]


def case_sign(d, env):
    pdf(os.path.join(d, "contract.pdf"), "Agreement")
    env["SAKURA_HOME"] = os.path.join(d, ".sakura")
    return "sign contract.pdf with my own key", [r"(^|/| )conv\s+sign\b"], [ONLINE, r"docusign"]


def case_strip(d, env):
    photo(os.path.join(d, "IMG_001.jpg"))
    photo(os.path.join(d, "IMG_002.jpg"))
    return "strip the location and camera data from these two photos before I share them", [r"(^|/| )conv\s+strip\b"], [ONLINE]


def case_audio(d, env):
    clip(os.path.join(d, "talk.mp4"))
    return "take the audio out of talk.mp4 as an mp3", [r"(^|/| )conv\s+(audio\b|\S*talk\.mp4\s+--to\s+mp3)"], [ONLINE, r"(^|[;&|]\s*)ffmpeg\b"]


def case_dupes(d, env):
    os.makedirs(os.path.join(d, "photos", "old"))
    photo(os.path.join(d, "photos", "x.jpg"))
    import shutil
    shutil.copy(os.path.join(d, "photos", "x.jpg"), os.path.join(d, "photos", "old", "x copy.jpg"))
    return "find duplicate files under photos/ (just show me, don't delete)", [r"(^|/| )dupes\b"], [r"\bfdupes\b", r"\brdfind\b", r"\bmd5sum\b.*\|.*\b(sort|uniq)\b"]


def case_shelve(d, env):
    os.makedirs(os.path.join(d, "dump"))
    photo(os.path.join(d, "dump", "a.jpg"))
    photo(os.path.join(d, "dump", "b.jpg"))
    return "sort the photos in dump/ into folders by the year and month they were taken, into library/", [r"(^|/| )shelve\b"], [r"\bexiftool\b.*Directory"]


def case_money(d, env):
    open(os.path.join(d, "nabil-2026-03.csv"), "w").write("Date,Description,Amount,Balance\n2026-03-01,SALARY,120000.00,150000.00\n2026-03-03,KFC,-1350.00,148650.00\n")
    env["SAKURA_MONEY_DIR"] = os.path.join(d, ".money")
    return "import this bank statement nabil-2026-03.csv into my accounts", [r"(^|/| )money\s+import\b"], [r"\bmint\.com\b|\bynab\b"]


def case_doctor(d, env):
    return "check that my sakura install is whole", [r"(^|/| )sakura-doctor\b"], []


def case_vid(d, env, server):
    return f"keep this video for good, with its metadata: {server}/grandma.mp4", [r"(^|/| )vid\b"], [r"(^|[;&|]\s*)yt-dlp\b", r"(^|[;&|]\s*)(curl|wget)\b", ONLINE]


def case_drift(d, env):
    for h in ("alpha", "beta"):
        os.makedirs(os.path.join(d, "hosts", h, "etc"))
        open(os.path.join(d, "hosts", h, "etc", "nginx.conf"), "w").write(f"worker_processes {4 if h == 'alpha' else 8};\n")
    fake = os.path.join(d, "fakessh")
    open(fake, "w").write(f"""#!/bin/sh
while [ "$1" = "-o" ]; do shift 2; done
host=$1; cmd=$2; root={d}/hosts/$host
[ -d "$root" ] || {{ echo "ssh: Could not resolve hostname $host" >&2; exit 255; }}
cmd=$(printf '%s' "$cmd" | sed "s#/etc/#$root/etc/#g"); sh -c "$cmd"
""")
    os.chmod(fake, 0o755)
    env["SAKURA_SSH"] = fake
    cfg = os.path.join(d, "ssh_config")
    open(cfg, "w").write("Host alpha\n    HostName 127.0.0.1\nHost beta\n    HostName 127.0.0.1\n")
    env["SAKURA_SSH_CONFIG"] = cfg
    return "how does /etc/nginx/nginx.conf differ between alpha and beta?", [r"(^|/| )drift\b"], [r"(^|[;&|]\s*)ssh\s+\w+\s+(cat|diff|md5sum|sha)"]


CASES = {"space": case_space, "ports": case_ports, "when": case_when, "merge": case_merge, "docx": case_docx, "redact": case_redact, "sign": case_sign,
         "strip": case_strip, "audio": case_audio, "dupes": case_dupes, "shelve": case_shelve, "money": case_money, "doctor": case_doctor, "vid": case_vid, "drift": case_drift}


def run_sakura(prompt, cwd, env, timeout):
    cmd = [LAUNCH, "--exec", "--skip-git-repo-check", "--json", prompt]
    commands, answer = [], ""
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        out = p.stdout
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or "")
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        item = ev.get("item", {})
        if ev.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands.append(item.get("command", ""))
        if ev.get("type") == "item.completed" and item.get("type") == "agent_message" and item.get("text"):
            answer = item["text"]
    return commands, answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--timeout", type=int, default=420)
    a = ap.parse_args()
    if a.list:
        print("\n".join(CASES))
        return 0
    if not (os.path.exists(os.path.expanduser("~/.local/bin/sakura")) or subprocess.run(["bash", "-c", "command -v sakura"], capture_output=True).returncode == 0):
        print("toolpick: the sakura binary isn't installed; nothing to measure here", file=sys.stderr)
        return 2
    www = tempfile.mkdtemp(prefix="toolpick-www-")
    clip(os.path.join(www, "grandma.mp4"))
    handler = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
    srv = socketserver.TCPServer(("127.0.0.1", 0), lambda *x, **k: handler(*x, directory=www, **k))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    server = f"http://127.0.0.1:{srv.server_address[1]}"
    results, passed, total = [], 0, 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        d = tempfile.mkdtemp(prefix=f"toolpick-{name}-")
        env = dict(os.environ, SAKURA_MEMORY_DIR=os.path.join(d, ".mem"), SAKURA_VID_DIR=os.path.join(d, ".vid"), SAKURA_VID_VIDEOS=os.path.join(d, "videos"))
        prompt, expect, forbid = fn(d, env, server) if name == "vid" else fn(d, env)
        t0 = time.time()
        commands, answer = run_sakura(prompt, d, env, a.timeout)
        joined = "\n".join(commands)
        picked = all(any(re.search(rx, c) for c in commands) for rx in expect)
        avoided = not any(re.search(rx, c, re.I) for rx in forbid for c in commands)
        clean_answer = not re.search(ONLINE, answer, re.I)
        ok = picked and avoided and clean_answer
        total += 1
        passed += ok
        why = [] if ok else ([f"expected {expect}"] if not picked else []) + ([f"ran a forbidden alternative"] if not avoided else []) + ([] if clean_answer else ["the answer names a web service"])
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.time() - t0:.0f}s)" + ("" if ok else f"  — {'; '.join(why)}\n         ran: {joined[:300] or '(nothing)'}"))
        results.append({"case": name, "prompt": prompt, "passed": ok, "commands": commands, "answer": answer[-800:], "seconds": round(time.time() - t0)})
    srv.shutdown()
    os.makedirs(os.path.join(ROOT, "evals", "results"), exist_ok=True)
    out = os.path.join(ROOT, "evals", "results", f"toolpick-{time.strftime('%Y%m%d-%H%M%S')}.json")
    json.dump({"passed": passed, "total": total, "cases": results}, open(out, "w"), indent=1)
    print(f"\n{passed}/{total}  ({out})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
