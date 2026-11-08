#!/usr/bin/env python3
"""Do the abilities do what they say, with no model's word for it? Each case plants known input and grades the output
against it: OCR of a generated image, a receipt into a ledger row, a schema from a migration, a process watcher firing,
a DuckDB query, an offer that runs once, a docs pack that rag finds, a worker in a worktree (the one case that uses a
model), fleet over a test ssh config.

  evals/abilities.py              every case
  evals/abilities.py --only NAME
"""
import argparse
import json
import os
import subprocess
import tempfile
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")


def run(cmd, env=None, cwd=None, stdin=None, timeout=600, shell=False):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(cmd, env=e, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=timeout, shell=shell)


def image(path, lines):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except OSError:
        font = None
    im = Image.new("RGB", (560, 40 + 46 * len(lines)), "white")
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        d.text((20, 20 + i * 46), l, fill="black", font=font)
    im.save(path)


def look_ocr(tmp):
    p = os.path.join(tmp, "t.png")
    image(p, ["Hello 4060", "ERROR: disk full on /dev/sda1"])
    out = run([os.path.join(BIN, "look"), "--text", p]).stdout
    return {"OCR reads the lines": "Hello 4060" in out and "disk full" in out}


def look_vision(tmp):
    p = os.path.join(tmp, "t.png")
    image(p, ["Hello 4060"])
    r = run([os.path.join(BIN, "look"), p, "What text is in this image? Reply with only the text."], timeout=400)
    return {"the vision model reads the text": "4060" in r.stdout, "it names the model it used": "[look:" in r.stdout}


def ledger(tmp):
    p = os.path.join(tmp, "r.png")
    image(p, ["Bhatbhateni Supermarket", "Date: 2026-11-07", "Rice 5kg        Rs 850.00", "Milk 1L         Rs 120.00", "Total           Rs 970.00", "Thank you"])
    env = {"SAKURA_HOME": os.path.join(tmp, "home")}
    run([os.path.join(BIN, "ledger"), "add", p, "weekly"], env)
    rows = run([os.path.join(BIN, "ledger"), "csv"], env).stdout
    total = run([os.path.join(BIN, "ledger"), "sum", "2026-11"], env).stdout
    return {"the amount is the total, not a line": ",970.00,NPR," in rows, "the date and vendor are read": "2026-11-07,Bhatbhateni" in rows,
            "the receipt image is kept": os.path.isdir(os.path.join(tmp, "home", "ledger")) and os.listdir(os.path.join(tmp, "home", "ledger")),
            "sum adds up": "970.00 NPR" in total}


def schema(tmp):
    d = os.path.join(tmp, "lar", "database", "migrations")
    os.makedirs(d)
    open(os.path.join(d, "2026_01_01_000000_x.php"), "w").write("""<?php
Schema::create('customers', function (Blueprint $table) { $table->id(); $table->string('name'); $table->timestamps(); });
Schema::create('orders', function (Blueprint $table) { $table->id(); $table->foreignId('customer_id')->constrained()->cascadeOnDelete(); $table->decimal('amount', 10, 2); $table->timestamps(); });
Schema::table('customers', function (Blueprint $table) { $table->string('phone')->nullable(); });
""")
    open(os.path.join(tmp, "lar", "extra.sql"), "w").write("CREATE TABLE invoices (id int primary key, order_id int, FOREIGN KEY (order_id) REFERENCES orders(id));\n")
    env = {"XDG_CACHE_HOME": os.path.join(tmp, "cache")}
    root = os.path.join(tmp, "lar")
    all_ = run([os.path.join(BIN, "schema"), root], env).stdout
    refs = run([os.path.join(BIN, "schema"), root, "refs", "customer_id"], env).stdout
    table = run([os.path.join(BIN, "schema"), root, "customers"], env).stdout
    return {"three tables found": all(t in all_ for t in ("customers", "orders", "invoices")),
            "the Laravel foreign key points at customers": "orders.customer_id -> customers" in refs,
            "the SQL foreign key is read": "order_id->orders" in all_,
            "a later alter adds the column": "phone" in table, "referenced-by is shown": "referenced by: orders.customer_id" in table}


def procwatch(tmp):
    env = {"SAKURA_PROCS_DIR": os.path.join(tmp, "procs")}
    pw = os.path.join(BIN, "procwatch")
    marker = os.path.join(tmp, "fired")
    run([pw, "start", "t", "--", "bash", "-c", "sleep 1; echo warming; sleep 1; echo READY now; sleep 20"], env, cwd=tmp)
    run([pw, "on", "t", "READY", "--", "bash", "-c", f"echo $PROCWATCH_LINE > {marker}"], env)
    w = run([pw, "wait", "t", "READY", "10"], env)
    time.sleep(1.5)
    listed = run([pw, "list"], env).stdout
    run([pw, "stop", "t"], env)
    gone = run([pw, "list"], env).stdout
    return {"wait returns the matching line": w.returncode == 0 and "READY now" in w.stdout,
            "on fires with the line": os.path.exists(marker) and "READY now" in open(marker).read(),
            "list shows it running": "running" in listed and " t " in listed, "stop stops it": "stopped" in gone}


def dq(tmp):
    p = os.path.join(tmp, "o.csv")
    open(p, "w").write("city,amount\nKtm,10\nPkr,5\nKtm,7\n")
    out = run([os.path.join(BIN, "dq"), "--csv", "select city, sum(amount) s from t group by 1 order by 2 desc", p], timeout=300).stdout
    sch = run([os.path.join(BIN, "dq"), "--schema", p], timeout=120).stdout
    return {"the query is right": out.splitlines()[1:3] == ["Ktm,17", "Pkr,5"], "schema shows the columns": "amount" in sch and "BIGINT" in sch}


def offer(tmp):
    env = {"SAKURA_PA_DIR": os.path.join(tmp, "pa"), "SAKURA_PA_NO_TIMER": "1", "SAKURA_PA_NOTIFY": "/bin/true"}
    pa = os.path.join(BIN, "pa")
    o = run([pa, "offer", "make a marker", "--", "bash", "-c", "echo x >> marker"], env, cwd=tmp).stdout
    oid = o.split("offer ")[1].split(":")[0] if "offer " in o else ""
    bad = run([pa, "yes", "nope"], env, cwd=tmp)
    first = run([pa, "yes", oid], env, cwd=tmp)
    second = run([pa, "yes", oid], env, cwd=tmp)
    count = open(os.path.join(tmp, "marker")).read().count("x") if os.path.exists(os.path.join(tmp, "marker")) else 0
    return {"yes runs the offered command": first.returncode == 0 and count == 1, "it runs once only": second.returncode != 0 and count == 1,
            "an unknown id does nothing": bad.returncode != 0}


def docpack(tmp):
    src = os.path.join(tmp, "docs-src")
    os.makedirs(src)
    open(os.path.join(src, "routing.md"), "w").write("# Routing\n\nThe zebra-route middleware limits requests to 42 per minute.\n")
    run("git init -q -b main . && git config user.email t@t && git config user.name t && git add . && git commit -qm d", shell=True, cwd=src)
    env = {"SAKURA_HOME": os.path.join(tmp, "home"), "SAKURA_RAG_DB": os.path.join(tmp, "rag.db")}
    add = run([os.path.join(BIN, "docpack"), "add", "zebra", src, "main"], env, timeout=600)
    found = run([os.path.join(BIN, "rag"), "search", "zebra-route limit per minute"], env, timeout=300).stdout
    snap = run([os.path.join(BIN, "docpack"), "snapshot"], env).stdout
    return {"the pack is fetched and indexed": add.returncode == 0, "rag finds the line": "42 per minute" in found,
            "sessions are told about it": "zebra" in snap}


def fleet(tmp):
    cfg = os.path.join(tmp, "ssh_config")
    open(cfg, "w").write("Host nowhere\n    HostName 127.0.0.1\n    Port 1\nHost github.com\n    User git\n")
    out = run([os.path.join(BIN, "fleet")], {"SAKURA_SSH_CONFIG": cfg}, timeout=60).stdout
    return {"a dead host is down, not an error": "down" in out and "nowhere" in out, "github.com is skipped": "github" not in out}


def worktree(tmp):
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    open(os.path.join(repo, "a.txt"), "w").write("a\n")
    run("git init -q -b main . && git config user.email t@t && git config user.name t && git add . && git commit -qm i", shell=True, cwd=repo)
    env = {"XDG_CACHE_HOME": os.path.join(tmp, "cache")}
    r = run([os.path.join(BIN, "sakura-worker")], env, cwd=repo, stdin="worktree: yes\nverify: test -f b.txt\ntimeout: 400\n\nCreate b.txt containing the word hello.\n", timeout=1500)
    wt = next((l.split()[1] for l in r.stdout.splitlines() if l.startswith("worktree: ")), "")
    clean = run(["git", "status", "--porcelain"], cwd=repo).stdout.strip() == ""
    print("  ", r.stdout.splitlines()[0] if r.stdout else r.stderr[-200:])
    ok = "WORKER PASSED" in r.stdout and wt and os.path.exists(os.path.join(wt, "b.txt"))
    if wt:
        run(["git", "worktree", "remove", "--force", wt], cwd=repo)
    return {"the worker passed in a worktree": bool(ok), "the main checkout is untouched": clean}


def tbl(tmp):
    t = os.path.join(BIN, "tbl")
    ps = run([t, "-c", "3"], stdin="USER PID COMMAND\nroot 1 /sbin/init splash\nme 22 bash -lc x\n").stdout
    csvs = run([t, "--sort", "2", "--desc", "--md"], stdin="city,amount\nKtm,10\nPkr,5\nBkt,70\n").stdout.splitlines()
    js = run([t, "-k", "unit,msg"], stdin='{"unit":"nginx","msg":"boom","x":1}\n{"unit":"php","msg":"bang","x":2}\n').stdout
    cnt = run([t, "--count"], stdin="k\na\nb\na\na\n").stdout.splitlines()
    return {"whitespace columns, last one swallows the rest": "/sbin/init splash" in ps and "bash -lc x" in ps,
            "csv sorted numerically, as markdown": csvs[2].startswith("| Bkt") and csvs[4].startswith("| Pkr"),
            "json lines with chosen keys": "nginx" in js and "boom" in js and "x" not in js.splitlines()[0],
            "count groups and ranks": cnt[2].startswith("3") and "a" in cnt[2]}


def logs_local(tmp):
    import random, string
    marker = "sakura-abilities-" + "".join(random.choices(string.ascii_lowercase, k=8))  # letters: digits are collapsed when grouping
    for _ in range(3):
        subprocess.run(["logger", "-p", "user.err", "-t", "sakura-eval", f"{marker} failed: code {os.getpid()}"], check=False)
    time.sleep(1.5)
    out = run([os.path.join(BIN, "logs"), "--since", "5m"]).stdout
    line = next((l for l in out.splitlines() if marker in l), "")
    raw = run([os.path.join(BIN, "logs"), "--since", "5m", "--raw"]).stdout
    return {"a planted error shows up grouped with its count": line.startswith("3\t"), "the source is the tag": "sakura-eval" in line,
            "the table has a header": out.startswith("count\tfirst\tlast\tsource\tmessage"), "--raw lists the lines": raw.count(marker) == 3}


def decide(tmp):
    env = {"SAKURA_HOME": os.path.join(tmp, "home")}
    repo = os.path.join(tmp, "r")
    os.makedirs(repo)
    subprocess.run("git init -q -b main . && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m i", shell=True, cwd=repo)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    run([os.path.join(BIN, "sakura-decide"), "Redis for the queue: LISTEN/NOTIFY dropped jobs"], env, cwd=repo)
    why = run([os.path.join(BIN, "sakura-decide"), "why", "queue"], env, cwd=repo).stdout
    none = run([os.path.join(BIN, "sakura-decide"), "why", "zebra"], env, cwd=repo)
    recall = run([os.path.join(BIN, "sakura-recall"), "LISTEN NOTIFY"], dict(env, SAKURA_SESSIONS_DIR=os.path.join(tmp, "none"), XDG_CACHE_HOME=os.path.join(tmp, "cache"))).stdout
    return {"why finds it with repo, branch and commit": "Redis" in why and f"main@{sha}" in why, "an unknown topic says so": none.returncode == 1,
            "recall finds decisions too": "[decision]" in recall and "Redis" in recall}


def clip(tmp):
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return {"skipped: no display": True}
    marker = f"sakura-clip-{os.getpid()}"
    run([os.path.join(BIN, "clip"), "set"], stdin=marker, timeout=15)
    out = run([os.path.join(BIN, "clip")], timeout=15).stdout
    return {"set then get round-trips": out.strip() == marker}


def status(tmp):
    env = {"SAKURA_HOME": os.path.join(tmp, "home"), "SAKURA_TONIGHT_DIR": os.path.join(tmp, "tonight"), "SAKURA_TONIGHT_NO_TIMER": "1",
           "SAKURA_PA_DIR": os.path.join(tmp, "pa"), "SAKURA_PA_NO_TIMER": "1", "SAKURA_PA_NOTIFY": "/bin/true", "SAKURA_GUARDIAN_DIR": os.path.join(tmp, "g")}
    run([os.path.join(BIN, "sakura-tonight"), "a job for tonight"], env, cwd=tmp)
    run([os.path.join(BIN, "pa"), "offer", "x", "--", "true"], env, cwd=tmp)
    short = run([os.path.join(BIN, "sakura-status")], env).stdout.strip()
    longer = run([os.path.join(BIN, "sakura-status"), "--long"], env).stdout
    return {"the short line counts the queue and offers": "☾1" in short and "?1" in short, "the long line says it in words": "1 queued tonight" in longer and "1 offers" in longer}


def watch(tmp):
    r = subprocess.run(["timeout", "3.5", os.path.join(BIN, "sakura-watch"), "-n", "1", "date +%s%N | cut -c1-12"], capture_output=True, text=True)
    lines = r.stdout.splitlines()
    return {"it reruns and marks what changed": any(l.startswith("- ") for l in lines) and any(l.startswith("+ ") for l in lines),
            "it counts the changes in the header": any("change" in l and "every 1s" in l for l in lines)}


CASES = {"tbl": tbl, "logs": logs_local, "decide": decide, "clip": clip, "status": status, "watch": watch, "look-ocr": look_ocr, "look-vision": look_vision, "ledger": ledger, "schema": schema, "procwatch": procwatch, "dq": dq,
         "offer": offer, "docpack": docpack, "fleet": fleet, "worktree": worktree}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    passed = total = 0
    for name, case in CASES.items():
        if args.only and args.only != name:
            continue
        with tempfile.TemporaryDirectory(dir=os.path.expanduser("~/.cache")) as tmp:
            print(f"\n== {name}", flush=True)
            try:
                results = case(tmp)
            except Exception as e:
                results = {f"ran without crashing ({e})": False}
            for check, ok in results.items():
                print(f"  {'ok  ' if ok else 'FAIL'} {check}", flush=True)
                total += 1
                passed += bool(ok)
    print(f"\nabilities: {passed}/{total}")


if __name__ == "__main__":
    main()
