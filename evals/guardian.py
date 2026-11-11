#!/usr/bin/env python3
"""The guardian, graded by planted state: disks and a fortnight of samples with a known growth rate, certificates made
here with a known end date, backup directories with known ages, and a clock the eval sets. Checks that read the real
machine (swap, systemd, the GPU) are left out: what they find depends on where this runs.

  evals/guardian.py              every case
  evals/guardian.py --only NAME  one of: projection disks certs backups tick
No model, no network.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
G = os.path.join(BIN, "sakura-guardian")
NOW = 1794300000  # 2026-11-10, a fixed clock
DAY = 86400
GIB = 1024 ** 3


def env_for(tmp, now=NOW, mounts=None):
    e = dict(os.environ)
    e.pop("NTFY_TOPIC", None)
    gdir = os.path.join(tmp, "guardian")
    os.makedirs(gdir, exist_ok=True)
    mp = os.path.join(tmp, "mounts.json")
    json.dump(mounts or [], open(mp, "w"))
    e.update({"SAKURA_GUARDIAN_DIR": gdir, "SAKURA_GUARDIAN_NOW": str(now), "SAKURA_GUARDIAN_MOUNTS": mp, "HOME": tmp})
    return e


def show(env, *args):
    r = subprocess.run([G, "--json", *args], env=env, capture_output=True, text=True, timeout=120)
    d = json.loads(r.stdout or "{}")
    return r, [f["text"] for f in d.get("findings", [])], [f["text"] for f in d.get("ok", [])]


def disk(mount, total_g, used_g):
    return {"mount": mount, "total": total_g * GIB, "used": int(used_g * GIB), "avail": int((total_g - used_g) * GIB)}


def samples(tmp, series):
    """series: {mount: [used GiB, oldest first, one a day, the last one yesterday]}"""
    n = max(len(v) for v in series.values())
    with open(os.path.join(tmp, "guardian", "disk.jsonl"), "w") as f:
        for i in range(n):
            f.write(json.dumps({"t": NOW - (n - i) * DAY, "d": {m: int(v[i] * GIB) for m, v in series.items() if i < len(v)}}) + "\n")


def projection(tmp):
    mounts = [disk("/steady", 100, 63), disk("/step", 400, 150), disk("/shrinking", 100, 40), disk("/new", 100, 50), disk("/noisy", 200, 100)]
    env = env_for(tmp, mounts=mounts)
    samples(tmp, {
        "/steady": [50 + i for i in range(13)],                # 1 GiB a day, 37 GiB left: 37 days
        "/step": [100] * 12 + [150],                           # flat, then one 50 GiB download yesterday
        "/shrinking": [60 - i for i in range(13)],
        "/new": [49.5],                                        # one day of samples
        "/noisy": [74 + 2 * i + (3 if i % 2 else -3) for i in range(13)],  # 2 GiB a day under ±3 of noise, 100 left: ~50 days
    })
    _, findings, ok = show(env, "--all")
    by = {m["mount"]: next((t for t in findings + ok if t.startswith(m["mount"] + ":")), "") for m in mounts}
    days = {k: int(v.split("full in about ")[1].split()[0]) if "full in about" in v else None for k, v in by.items()}
    # the same steady disk with 9 GiB left: full within the fortnight, so it's a finding, not a footnote
    env2 = env_for(tmp, mounts=[disk("/steady", 72, 63)])
    _, soon, _ = show(env2)
    # samples from the future (a clock that was wrong) and from before the fortnight don't count
    env3 = env_for(tmp, mounts=[disk("/steady", 100, 63)])
    with open(os.path.join(tmp, "guardian", "disk.jsonl"), "a") as f:
        f.write(json.dumps({"t": NOW + 30 * DAY, "d": {"/steady": 1 * GIB}}) + "\n")
        f.write(json.dumps({"t": NOW - 60 * DAY, "d": {"/steady": 62 * GIB}}) + "\n")
    _, f3, ok3 = show(env3, "--all")
    line3 = next((t for t in f3 + ok3 if t.startswith("/steady:")), "")
    return {
        "1 GiB a day with 37 GiB left is 37 days": days["/steady"] == 37,
        "one big download is a step, not a trend": days["/step"] is None,
        "a disk that's emptying has no date": days["/shrinking"] is None,
        "one day of samples is too little to say": days["/new"] is None,
        "2 GiB a day under noise still comes out near 50 days": days["/noisy"] is not None and 44 <= days["/noisy"] <= 56,
        "far-off dates are a footnote, not a finding": not any(t.startswith(("/steady", "/noisy")) for t in findings),
        "full within a fortnight is a finding": any(t.startswith("/steady:") and "full in about 9 days" in t for t in soon),
        "samples from the future or older than a fortnight are ignored": "full in about 37 days" in line3,
    }


def disks(tmp):
    env = env_for(tmp, mounts=[disk("/", 100, 95), disk("/data", 100, 91), disk("/fine", 100, 20)])
    r, findings, ok = show(env, "--all")
    root = next((t for t in findings if t.startswith("/:")), "")
    data = next((t for t in findings if t.startswith("/data:")), "")
    return {
        "95% used is a finding that points at space": "95% used" in root and "`space`" in root and "5.0G free" in root,
        "another mount gets its own space line": "`space /data`" in data,
        "20% used is not": any(t.startswith("/fine: 20% used") for t in ok) and not any(t.startswith("/fine") for t in findings),
        "findings exit 1": r.returncode == 1,
    }


def certs(tmp):
    env = env_for(tmp)
    paths = []
    for name, days in (("soon.example", 10), ("fine.example", 200)):
        key, crt = os.path.join(tmp, name + ".key"), os.path.join(tmp, name + ".crt")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt, "-days", str(days),
                        "-subj", f"/CN={name}"], capture_output=True, check=True)
        paths.append(crt)
    json.dump({"certs": paths + [os.path.join(tmp, "gone.crt")]}, open(os.path.join(tmp, "guardian", "config.json"), "w"))
    real = dict(env)
    real.pop("SAKURA_GUARDIAN_NOW")  # the certificates were made now, so they're judged now
    r, findings, ok = show(real, "--all")
    later = dict(real, SAKURA_GUARDIAN_NOW=str(__import__("time").time() + 185 * DAY))
    _, f2, _ = show(later, "--all")
    soon = [t for t in findings if "soon.example" in t]
    return {
        "a certificate ending in 10 days is a finding with its path": len(soon) == 1 and ("ends in 9 days" in soon[0] or "ends in 10 days" in soon[0]) and paths[0] in soon[0],
        "one with 200 days is only listed": any("fine.example" in t for t in ok) and not any("fine.example" in t for t in findings),
        "a path that's gone is skipped, and nothing is written to stderr": "Traceback" not in r.stderr and "Warning" not in r.stderr,
        "185 days on, the second one is due too": any("fine.example" in t and "ends in 1" in t for t in f2),
    }


def backups(tmp):
    env = env_for(tmp)

    def g(*args, now=None):
        return subprocess.run([G, *args], env=dict(env, SAKURA_GUARDIAN_NOW=str(now or NOW)), capture_output=True, text=True, timeout=120)

    fresh, late = os.path.join(tmp, "fresh"), os.path.join(tmp, "late")
    for d, age in ((fresh, 0.5), (late, 5)):
        os.makedirs(os.path.join(d, "data"))
        p = os.path.join(d, "data", "pack")
        open(p, "w").write("x")
        for q in (p, os.path.join(d, "data"), d):
            os.utime(q, (NOW - age * DAY, NOW - age * DAY))
    g("backup", "photos", fresh)
    g("backup", "mail", late, "--every", "3")
    g("backup", "gone", os.path.join(tmp, "nowhere"))
    _, f1, ok1 = show(env, "--all")
    b1 = [t for t in f1 if t.startswith("backup")]
    restored = g("restored", "photos")
    _, f2, ok2 = show(env, "--all")
    _, f3, _ = show(dict(env, SAKURA_GUARDIAN_NOW=str(NOW + 91 * DAY)))
    conf = json.load(open(os.path.join(tmp, "guardian", "config.json")))
    g("backup", "photos", fresh, "--every", "7")
    kept = json.load(open(os.path.join(tmp, "guardian", "config.json")))["backups"]["photos"]
    forgot = g("forget", "mail")
    _, f4, _ = show(env)
    return {
        "a backup unchanged for 5 days when it should change every 3 is late": any("backup mail: last changed 5.0 days ago" in t and "every 3" in t for t in b1),
        "a fresh one isn't late": any("backup photos: last changed 0.5 days ago" in t for t in ok1),
        "one that was never test-restored is a finding": any("photos has never been test-restored" in t for t in b1),
        "a path that isn't there says so": any("backup gone" in t and "isn't there" in t for t in b1),
        "restored clears it, stamped with the clock": restored.returncode == 0 and conf["backups"]["photos"]["restored"] == NOW
        and not any("photos" in t for t in f2) and any("photos: test-restored 0 days ago" in t for t in ok2),
        "91 days later it nags again": any("photos: last test-restore 91 days ago" in t for t in f3),
        "registering again keeps the restore date": kept.get("restored") == NOW and kept.get("every") == 7,
        "forget stops the watching": forgot.returncode == 0 and not any("backup mail" in t for t in f4),
    }


def tick(tmp):
    mounts = [disk("/", 100, 95)]
    env = env_for(tmp, mounts=mounts)

    def t(now):
        return subprocess.run([G, "tick"], env=dict(env, SAKURA_GUARDIAN_NOW=str(now)), capture_output=True, text=True, timeout=120).stdout

    first, again, next_day, week = t(NOW), t(NOW + 3600), t(NOW + DAY), t(NOW + 7 * DAY)
    lines = [json.loads(x) for x in open(os.path.join(tmp, "guardian", "disk.jsonl"))]
    seen = json.load(open(os.path.join(tmp, "guardian", "seen.json")))
    return {
        "the first tick says the finding": "/: 95% used" in first,
        "the same finding isn't repeated that day or the next": "/: 95% used" not in again and "/: 95% used" not in next_day,
        "a week on it's said again": "/: 95% used" in week,
        "each tick records a sample of every disk at the clock's time": [x["t"] for x in lines] == [NOW, NOW + 3600, NOW + DAY, NOW + 7 * DAY]
        and all(x["d"] == {"/": 95 * GIB} for x in lines),
        "what was said is remembered with when": any(k.startswith("/: 95% used") and v == NOW + 7 * DAY for k, v in seen.items()),
    }


CASES = {"projection": projection, "disks": disks, "certs": certs, "backups": backups, "tick": tick}


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
            except Exception as e:
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
