#!/usr/bin/env python3
"""The machine room: ports, space, drift, when, sakura-notes and host-scoped memory, graded by planted state, never by
what a tool prints about itself. ports is graded by a socket this eval opens; space by byte counts in a planted home, a
symlink that must not be followed and files that must survive; drift by a fake ssh that serves three planted hosts; when by
exact timestamps from a fixed --now; sakura-notes by a temp repo with a tag; memory by the snapshot under two hostnames.

  evals/machineroom.py              every case
  evals/machineroom.py --only NAME  one of: ports space drift when notes memory
No model, no network.
"""
import argparse
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")


def run(args, env=None, cwd=None, stdin=None, timeout=120):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(args, env=e, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=timeout)


def blob(path, size, mtime_days_ago=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(os.urandom(size))
    if mtime_days_ago is not None:
        t = time.time() - mtime_days_ago * 86400
        os.utime(path, (t, t))


def ports(tmp):
    tcp = socket.socket()
    tcp.bind(("127.0.0.1", 0))
    tcp.listen(1)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))
    tport, uport = tcp.getsockname()[1], udp.getsockname()[1]
    try:
        t = run([os.path.join(BIN, "ports"), str(tport)])
        u = run([os.path.join(BIN, "ports"), str(uport), "--json"])
        free = run([os.path.join(BIN, "ports"), "1"])
        all_ = run([os.path.join(BIN, "ports"), "--json"])
        me = str(os.getpid())
        urows = json.loads(u.stdout or "[]")
        rows = json.loads(all_.stdout or "[]")
    finally:
        tcp.close()
        udp.close()
    after = run([os.path.join(BIN, "ports"), str(tport)])
    return {"the tcp port names this process": f" {me} " in t.stdout and "tcp" in t.stdout and "python" in t.stdout,
            "the udp socket is found too, as json": any(r["proto"] == "udp" and str(r["pid"]) == me and r["port"] == uport for r in urows),
            "a free port says so and exits 1": "nothing listens on port 1" in free.stdout and free.returncode == 1,
            "the full list includes both": {tport, uport} <= {r["port"] for r in rows},
            "a closed socket is gone": "nothing listens" in after.stdout}


def space(tmp):
    home = os.path.join(tmp, "home")
    outside = os.path.join(tmp, "outside")
    sizes = {".cache/pip/a.bin": 3_000_000, ".cache/uv/b": 1_000_000, ".npm/_cacache/c": 2_000_000, "docs/thesis.pdf": 4_000_000,
             "proj/__pycache__/x.pyc": 1_000_000, "proj/node_modules/y": 2_000_000, ".local/share/Trash/files/z": 1_000_000}
    for rel, n in sizes.items():
        blob(os.path.join(home, rel), n)
    blob(os.path.join(home, "Downloads", "big.iso"), 5_000_000, mtime_days_ago=200)
    blob(os.path.join(outside, "precious"), 700_000)
    os.symlink(outside, os.path.join(home, ".cache", "evil"))
    env = {"HOME": home, "SAKURA_SPACE_NO_SUDO": "1"}
    sp = os.path.join(BIN, "space")
    report = json.loads(run([sp, "--json"], env).stdout)
    by = {r["what"]: r for r in report}
    dry = json.loads(run([sp, "clean", "--json"], env).stdout)
    untouched_after_dry = all(os.path.exists(os.path.join(home, rel)) for rel in sizes)
    go = run([sp, "clean", "--go", "--all-caches"], env)
    results = {
        "pip cache is measured (within 5%)": abs(by.get("pip cache", {}).get("bytes", 0) - 3_000_000) < 150_000,
        "a cache clears itself, node_modules is rebuildable, old downloads are kept":
            by.get("pip cache", {}).get("verdict") == "clears itself" and by.get("proj/node_modules", {}).get("verdict") == "rebuildable"
            and by.get("Downloads older than 90 days", {}).get("verdict") == "keep",
        "the dry run plans the safe set and nothing else": {i["what"] for i in dry["items"]} == {"pip cache", "uv cache", "npm cache", "trash", "__pycache__"} and dry["go"] is False,
        "the dry run deletes nothing": untouched_after_dry,
        "--go empties the safe set": not os.listdir(os.path.join(home, ".cache", "pip")) and not os.path.exists(os.path.join(home, "proj", "__pycache__", "x.pyc"))
                                      and not os.listdir(os.path.join(home, ".local", "share", "Trash")),
        "--go leaves downloads, documents and node_modules": all(os.path.exists(os.path.join(home, p)) for p in ("Downloads/big.iso", "docs/thesis.pdf", "proj/node_modules/y")),
        "the symlink out of ~ is not followed": os.path.exists(os.path.join(outside, "precious")) and go.returncode == 0,
    }
    top = run([sp, home], env).stdout.splitlines()
    results["space PATH ranks the biggest first"] = bool(top) and "Downloads" in top[0] and "docs" in top[1]
    return results


def sshkey(comment):
    key = os.urandom(32)
    data = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + key
    return f"ssh-ed25519 {base64.b64encode(data).decode()} {comment}"


def drift(tmp):
    hosts = {"alpha": {"etc/nginx.conf": "worker_processes 4;\nkeepalive 65;\n", "pkgs": "nginx 1.24\ncurl 8.5\nvim 9.1\n", "units": "nginx.service\nsshd.service\n"},
             "beta": {"etc/nginx.conf": "worker_processes 4;\nkeepalive 65;\n", "pkgs": "nginx 1.24\ncurl 8.4\n", "units": "nginx.service\nsshd.service\ndocker.service\n"},
             "gamma": {"etc/nginx.conf": "worker_processes 8;\nkeepalive 65;\n", "pkgs": "nginx 1.26\ncurl 8.5\nvim 9.1\n", "units": "nginx.service\nsshd.service\n"}}
    k1, k2 = sshkey("kai@laptop"), sshkey("old@desk")
    keys = {"alpha": k1 + "\n" + k2 + "\n", "beta": k1 + "\n", "gamma": k1 + "\n"}
    for h, files in hosts.items():
        for rel, text in files.items():
            p = os.path.join(tmp, h, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(text)
        open(os.path.join(tmp, h, "keys"), "w").write(keys[h])
    fake = os.path.join(tmp, "fakessh")
    open(fake, "w").write(f"""#!/bin/sh
while [ "$1" = "-o" ]; do shift 2; done
host=$1; cmd=$2; root={tmp}/$host
[ -d "$root" ] || {{ echo "ssh: Could not resolve hostname $host" >&2; exit 255; }}
case "$cmd" in
  *dpkg-query*) cat "$root/pkgs";;
  *list-unit-files*) cat "$root/units";;
  *authorized_keys*) cat "$root/keys";;
  *) cmd=$(printf '%s' "$cmd" | sed "s#/etc/#$root/etc/#g"); sh -c "$cmd";;
esac
""")
    os.chmod(fake, 0o755)
    env = {"SAKURA_SSH": fake}
    d = os.path.join(BIN, "drift")
    f = run([d, "/etc/nginx.conf", "alpha", "beta", "gamma", "dead"], env)
    same = run([d, "/etc/nginx.conf", "alpha", "beta"], env)
    pk = json.loads(run([d, "packages", "alpha", "beta", "gamma", "--json"], env).stdout)
    un = run([d, "units", "alpha", "beta", "gamma"], env).stdout
    ks = json.loads(run([d, "sshkeys", "alpha", "beta", "gamma", "--json"], env).stdout)
    pk_rows = {r["package"]: r for r in pk["rows"]}
    return {"same file hashes equal, the odd one differs, with a diff": "same" in f.stdout and "differs" in f.stdout and "-worker_processes 4;" in f.stdout and "+worker_processes 8;" in f.stdout,
            "a dead host is named, not fatal": "dead" in f.stdout and "unreachable" in f.stdout and f.returncode == 1,
            "identical files exit 0 with no diff": same.returncode == 0 and "+++" not in same.stdout,
            "packages: only the differing rows, with versions": set(pk_rows) == {"curl", "nginx", "vim"} and pk_rows["vim"]["beta"] == "-" and pk_rows["curl"]["beta"] == "8.4",
            "units: the one enabled on one host": "docker.service" in un and "sshd.service" not in un,
            "sshkeys: the stray key is on alpha only": len(ks["rows"]) == 1 and "old@desk" in ks["rows"][0]["key"] and ks["rows"][0]["alpha"] == "yes" and ks["rows"][0]["beta"] == "-"}


def when(tmp):
    w = os.path.join(BIN, "when")
    env = {"TZ": "Asia/Kathmandu"}
    now = ["--now", "2026-11-09 10:00"]

    def nexts(expr, n=3):
        out = json.loads(run([w, "-n", str(n), *now, "--json", expr], env).stdout)[0]
        return out.get("english", ""), [t[:16] for t in out.get("next", [])], out.get("error")

    e1, n1, _ = nexts("0 3 * * 1")
    e2, n2, _ = nexts("*/15 9-17 * * 1-5")
    e3, n3, _ = nexts("30 2 1 * *")
    e4, n4, _ = nexts("0 8 1,15 * 1", 4)
    e5, n5, _ = nexts("Mon..Fri *-*-* 09:00:00")
    e6, n6, _ = nexts("*:0/10")
    e7, n7, _ = nexts("0 0 * * 7", 2)
    _, _, err = nexts("61 * * * *")
    _, _, err2 = nexts("Funday 10:00")
    cron = run([w, "-"], env, stdin="SHELL=/bin/sh\n# c\n0 3 * * 1 /usr/bin/backup\n@reboot /usr/bin/x\n").stdout
    return {"a weekly cron: english and the next Mondays": e1 == "At 03:00 every Monday" and n1 == ["2026-11-16T03:00", "2026-11-23T03:00", "2026-11-30T03:00"],
            "steps and ranges, starting from now": "Every 15 minutes" in e2 and "Monday to Friday" in e2 and n2 == ["2026-11-09T10:15", "2026-11-09T10:30", "2026-11-09T10:45"],
            "monthly on the 1st, not only Sundays": n3 == ["2026-12-01T02:30", "2027-01-01T02:30", "2027-02-01T02:30"],
            "day-of-month OR weekday, as cron does": n4 == ["2026-11-15T08:00", "2026-11-16T08:00", "2026-11-23T08:00", "2026-11-30T08:00"],
            "systemd OnCalendar weekdays": "Monday to Friday" in e5 and n5 == ["2026-11-10T09:00", "2026-11-11T09:00", "2026-11-12T09:00"],
            "systemd minute steps": "Every 10 minutes" in e6 and n6 == ["2026-11-09T10:10", "2026-11-09T10:20", "2026-11-09T10:30"],
            "7 is Sunday": n7 == ["2026-11-15T00:00", "2026-11-22T00:00"],
            "unreadable input is refused, not guessed": bool(err) and bool(err2),
            "a crontab on stdin: every job, variables skipped": "/usr/bin/backup" in cron and "At every boot" in cron and "SHELL" not in cron}


def notes(tmp):
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)

    def g(*a):
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)

    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    open(os.path.join(repo, "VERSION"), "w").write("1.2.3\n")
    g("add", ".")
    g("commit", "-qm", "release: 1.2.2")
    g("tag", "v1.2.2")
    for name, msg in (("bin/thing", "feat(logs): a mute list for noise"), ("bin/fixme", "fix: an interrupted init resumes"), ("evals/thing.py", "test: thing proven"),
                      ("README.md", "docs: the layout table"), ("x", "tidy up")):
        p = os.path.join(repo, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(msg)
        g("add", ".")
        g("commit", "-qm", msg)
    out = run([os.path.join(BIN, "sakura-notes")], {"SAKURA_NOTES_REPO": repo}).stdout
    to = os.path.join(tmp, "notes.md")
    run([os.path.join(BIN, "sakura-notes"), "--to", to, "--version", "9.9.9"], {"SAKURA_NOTES_REPO": repo})
    written = open(to).read() if os.path.exists(to) else ""
    return {"the heading takes VERSION, the range the last tag": out.startswith("# Sakura 1.2.3") and "Since v1.2.2: 5 commits" in out,
            "grouped by prefix with the scope as lead": "## New\n- **logs:** A mute list for noise" in out and "## Fixed\n- An interrupted init resumes" in out and "## Proven" in out,
            "release commits are left out, unprefixed ones land in Also": "- Release" not in out and "- 1.2.2" not in out and "## Also\n- Tidy up" in out,
            "the footer names the evals and commands touched": "`evals/thing.py`" in out and "`thing`" in out,
            "--to writes the file with the given version": written.startswith("# Sakura 9.9.9")}


def memory(tmp):
    env = {"SAKURA_MEMORY_DIR": os.path.join(tmp, "mem")}
    m = os.path.join(BIN, "sakura-memory")
    for fact in ("host:eldayn staging runs on port 8081", "host:Starlight.local the GPU box", "the user prefers tables"):
        run([m, "add", "notes", fact], env)
    code = "import importlib.machinery as m; print(m.SourceFileLoader('x', %r).load_module().snapshot())" % m
    on_eldayn = run([sys.executable, "-c", code], {**env, "SAKURA_HOSTNAME": "eldayn.lan"}).stdout
    on_star = run([sys.executable, "-c", code], {**env, "SAKURA_HOSTNAME": "starlight"}).stdout
    elsewhere = run([sys.executable, "-c", code], {**env, "SAKURA_HOSTNAME": "laptop"}).stdout
    show = run([m, "show", "notes"], {**env, "SAKURA_HOSTNAME": "eldayn"}).stdout
    return {"a host's fact loads on that host, with the shared ones": "8081" in on_eldayn and "prefers tables" in on_eldayn and "GPU box" not in on_eldayn,
            "hostnames match short and case-insensitively": "GPU box" in on_star and "8081" not in on_star,
            "a third machine gets only the shared facts, and a count": "8081" not in elsewhere and "GPU box" not in elsewhere and "prefers tables" in elsewhere and "2 about other machines" in elsewhere,
            "show lists everything and marks the other machines'": show.count("another machine's") == 1 and "8081" in show}


def clip(path, seconds=2):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=160x120:rate=10",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path], check=True)


def conv(tmp):
    from PIL import Image
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas
    c = os.path.join(BIN, "conv")
    for n in ("a", "b"):
        cv = canvas.Canvas(os.path.join(tmp, n + ".pdf"))
        cv.setAuthor("Kai Secret")
        for i in range(3):
            cv.drawString(100, 700, f"{n} page {i + 1} hello")
            cv.showPage()
        cv.save()
    im = Image.new("RGB", (400, 300), "red")
    ex = im.getexif()
    ex[0x010F] = "SecretCam"
    im.save(os.path.join(tmp, "photo.jpg"), exif=ex.tobytes())
    open(os.path.join(tmp, "note.md"), "w").write("# Title\n\nHello *world*.\n")
    clip(os.path.join(tmp, "clip.mp4"))
    subprocess.run(["qpdf", "--encrypt", "s3cret", "owner", "256", "--", os.path.join(tmp, "a.pdf"), os.path.join(tmp, "locked.pdf")], check=True)
    sha_before = {f: open(os.path.join(tmp, f), "rb").read() for f in ("a.pdf", "photo.jpg", "clip.mp4", "note.md")}

    def go(*args, env=None):
        return run([c, *args], env, cwd=tmp, timeout=240)

    go("merge", "a.pdf", "b.pdf", "-o", "m.pdf")
    go("pages", "m.pdf", "2-3", "-o", "p.pdf")
    go("rotate", "a.pdf", "90", "-o", "r.pdf")
    go("split", "b.pdf")
    go("m.pdf", "--to", "txt")
    go("a.pdf", "--to", "png")
    go("compress", "m.pdf", "-o", "small.pdf")
    go("note.md", "--to", "html")
    go("note.md", "--to", "docx")
    go("photo.jpg", "--to", "png")
    go("strip", "photo.jpg", "-o", "clean.jpg")
    go("strip", "a.pdf", "-o", "aclean.pdf")
    go("audio", "clip.mp4", "--to", "wav")
    go("trim", "clip.mp4", "0.5", "1.5", "-o", "cut.mp4")
    go("gif", "clip.mp4", "--width", "80", "-o", "c.gif")
    ok_unlock = go("unlock", "locked.pdf", "-o", "open.pdf", env={"SAKURA_CONV_PASSWORD_FROM_ENV_FOR_TESTS": "1", "SAKURA_CONV_PASSWORD": "s3cret"})
    bad_unlock = go("unlock", "locked.pdf", "-o", "bad.pdf", env={"SAKURA_CONV_PASSWORD_FROM_ENV_FOR_TESTS": "1", "SAKURA_CONV_PASSWORD": "wrong"})
    dry = go("clip.mp4", "--to", "webm", "--dry")
    unknown = go("note.md", "--to", "mp3")
    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    pages = lambda f: len(PdfReader(p(f)).pages) if os.path.exists(p(f)) else -1  # noqa: E731
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p("cut.mp4")], capture_output=True, text=True).stdout.strip() if os.path.exists(p("cut.mp4")) else "0"
    return {"merge: 3 + 3 pages make 6": pages("m.pdf") == 6,
            "pages and rotate and split": pages("p.pdf") == 2 and pages("r.pdf") == 3 and PdfReader(p("r.pdf")).pages[0].get("/Rotate") == 90 and all(pages(f"b p{i}.pdf") == 1 for i in (1, 2, 3)),
            "pdf to text keeps the words; pdf to png makes a page each": os.path.exists(p("m.txt")) and "b page 2 hello" in open(p("m.txt")).read() and all(os.path.exists(p(f"a-{i}.png")) for i in (1, 2, 3)),
            "compress writes a pdf that still has its pages": pages("small.pdf") == 6,
            "markdown to html and docx (pandoc)": os.path.exists(p("note.html")) and "<em>world</em>" in open(p("note.html")).read() and os.path.getsize(p("note.docx")) > 1000,
            "jpg to png is a real png": os.path.exists(p("photo.png")) and open(p("photo.png"), "rb").read(4) == b"\x89PNG",
            "strip removes EXIF from a photo and the author from a pdf": os.path.exists(p("clean.jpg")) and not dict(Image.open(p("clean.jpg")).getexif()) and os.path.exists(p("aclean.pdf"))
                                                                        and (PdfReader(p("aclean.pdf")).metadata or {}).get("/Author") is None and "Kai Secret" not in open(p("aclean.pdf"), "rb").read().decode("latin1"),
            "audio track out as wav; trim cuts to about a second": os.path.exists(p("clip.wav")) and open(p("clip.wav"), "rb").read(4) == b"RIFF" and 0.5 <= float(probe or 0) <= 2.5,
            "gif made": os.path.exists(p("c.gif")) and open(p("c.gif"), "rb").read(3) == b"GIF",
            "unlock: the right password opens it, through a pipe not argv": ok_unlock.returncode == 0 and os.path.exists(p("open.pdf")) and PdfReader(p("open.pdf")).is_encrypted is False and "s3cret" not in ok_unlock.stdout,
            "unlock: a wrong password fails without a file": bad_unlock.returncode == 1 and not os.path.exists(p("bad.pdf")),
            "--dry prints the command and writes nothing": "libvpx-vp9" in dry.stdout and not os.path.exists(p("clip.webm")),
            "an impossible pair is refused": unknown.returncode == 1 and "don't know how" in unknown.stderr,
            "no input was ever modified": all(open(p(f), "rb").read() == b for f, b in sha_before.items())}


def vid(tmp):
    import http.server
    import socketserver
    import threading
    www = os.path.join(tmp, "www")
    os.makedirs(www)
    clip(os.path.join(www, "grandma_1998.mp4"))
    handler = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
    srv = socketserver.TCPServer(("127.0.0.1", 0), lambda *a, **k: handler(*a, directory=www, **k))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/grandma_1998.mp4"
    env = {"SAKURA_VID_DIR": os.path.join(tmp, "state"), "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"]}
    v = os.path.join(BIN, "vid")
    try:
        one = run([v, url, "--dir", os.path.join(tmp, "out")], env, timeout=240)
        first = run([v, "archive", url, "--name", "fam", "--dir", os.path.join(tmp, "arc"), "--fg"], env, timeout=240)
        second = run([v, "archive", url, "--name", "fam", "--dir", os.path.join(tmp, "arc"), "--fg"], env, timeout=240)
        status = run([v, "status"], env)
        dry = run([v, "--dry", "archive", url], env)
    finally:
        srv.shutdown()
    out = os.listdir(os.path.join(tmp, "out")) if os.path.isdir(os.path.join(tmp, "out")) else []
    arc = os.listdir(os.path.join(tmp, "arc")) if os.path.isdir(os.path.join(tmp, "arc")) else []
    meta = json.load(open(os.path.join(tmp, "state", "fam.json"))) if os.path.exists(os.path.join(tmp, "state", "fam.json")) else {}
    archive_file = open(os.path.join(tmp, "state", "fam.archive")).read() if os.path.exists(os.path.join(tmp, "state", "fam.archive")) else ""
    return {"a video lands as mp4 with its info.json beside it": one.returncode == 0 and any(f.endswith(".mp4") for f in out) and any(f.endswith(".info.json") for f in out),
            "the name carries the date and the id": any(f.startswith("20") and "[grandma_1998]" in f for f in out),
            "archive: the first run keeps it and records it": first.returncode == 0 and any(f.endswith(".mp4") for f in arc) and "grandma_1998" in archive_file,
            "archive: the second run fetches nothing new": second.returncode == 0 and meta.get("new") == 0 and meta.get("after") == 1 and len([f for f in arc if f.endswith(".mp4")]) == 1,
            "status shows the archive": "fam" in status.stdout and "ok" in status.stdout,
            "--dry shows the download archive and the metadata flags": "--download-archive" in dry.stdout and "--embed-metadata" in dry.stdout and "--write-info-json" in dry.stdout}


def extract(tmp):
    import io
    import tarfile
    import zipfile
    src = os.path.join(tmp, "src", "sub")
    os.makedirs(src)
    open(os.path.join(tmp, "src", "a.txt"), "w").write("hi\n")
    open(os.path.join(src, "b.txt"), "w").write("deep\n")
    with zipfile.ZipFile(os.path.join(tmp, "arc.zip"), "w") as z:
        z.write(os.path.join(tmp, "src", "a.txt"), "a.txt")
        z.write(os.path.join(src, "b.txt"), "sub/b.txt")
        z.writestr("../evil.txt", "pwn")
    with tarfile.open(os.path.join(tmp, "arc.tar.gz"), "w:gz") as t:
        t.add(os.path.join(tmp, "src", "a.txt"), "a.txt")
        ti = tarfile.TarInfo("../evil2.txt")
        ti.size = 3
        t.addfile(ti, io.BytesIO(b"pwn"))
        ln = tarfile.TarInfo("link")
        ln.type = tarfile.SYMTYPE
        ln.linkname = "/etc/passwd"
        t.addfile(ln)
    c = os.path.join(BIN, "conv")
    z = run([c, "extract", "arc.zip"], cwd=tmp)
    t = run([c, "extract", "arc.tar.gz", "--json"], cwd=tmp)
    rec = json.loads(t.stdout.strip().splitlines()[-1]) if t.stdout.strip() else {}
    zip_dir = os.path.join(tmp, "arc")
    return {"a zip lands in its own folder with its tree": os.path.exists(os.path.join(zip_dir, "a.txt")) and os.path.exists(os.path.join(zip_dir, "sub", "b.txt")) and "refused 1 entry" in z.stdout,
            "zip-slip: nothing lands outside the folder": not os.path.exists(os.path.join(tmp, "evil.txt")) and not os.path.exists(os.path.join(tmp, "evil2.txt")) and not os.path.exists(os.path.join(os.path.dirname(tmp), "evil.txt")),
            "a tar's escaping entry and its symlink are refused, the file kept": rec.get("refused") == 2 and rec.get("files") == 1 and not os.path.lexists(os.path.join(rec.get("out", tmp), "link")),
            "the second archive with the same stem gets a new folder": rec.get("out", "").endswith("arc (2)")}


def watch(tmp):
    import http.server
    import socketserver
    import threading
    www = os.path.join(tmp, "www")
    os.makedirs(www)
    for v in ("v1", "v2"):
        clip(os.path.join(www, v + ".mp4"), 1)
    page = lambda vids: open(os.path.join(www, "index.html"), "w").write("<html><body>" + "".join(f'<video src="{v}.mp4"></video>' for v in vids) + "</body></html>")  # noqa: E731
    page(["v1", "v2"])
    handler = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
    srv = socketserver.TCPServer(("127.0.0.1", 0), lambda *a, **k: handler(*a, directory=www, **k))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    env = {"SAKURA_VID_DIR": os.path.join(tmp, "state"), "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"]}
    v = os.path.join(BIN, "vid")
    try:
        first = run([v, "watch", url, "--name", "fam"], env, timeout=120)
        same = run([v, "watch", url, "--name", "fam"], env, timeout=120)
        clip(os.path.join(www, "v3.mp4"), 1)
        page(["v1", "v2", "v3"])
        new = run([v, "watch", url, "--name", "fam"], env, timeout=120)
        again = run([v, "watch", url, "--name", "fam"], env, timeout=120)
    finally:
        srv.shutdown()
    return {"the first look only takes stock, exit 0": first.returncode == 0 and "2 videos there now" in first.stdout,
            "nothing new is exit 0": same.returncode == 0 and "nothing new" in same.stdout,
            "a new entry is reported once, exit 1": new.returncode == 1 and "1 new" in new.stdout and "index-3" in new.stdout,
            "and is remembered": again.returncode == 0 and "nothing new" in again.stdout}


CASES = {"ports": ports, "space": space, "drift": drift, "when": when, "notes": notes, "memory": memory, "conv": conv, "vid": vid, "extract": extract, "watch": watch}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    total = passed = 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                results = fn(tmp)
            except Exception as e:  # a crash is a failure with a reason, not a stack trace in the summary
                results = {f"{name} ran without crashing": False}
                print(f"  {name}: {type(e).__name__}: {e}")
        for check, ok in results.items():
            total += 1
            passed += bool(ok)
            print(f"  {'PASS' if ok else 'FAIL'}  {name}: {check}")
    print(f"\n{passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
