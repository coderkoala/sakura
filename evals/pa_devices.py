#!/usr/bin/env python3
"""pa across devices: one firing on many machines, repeating calendar events, reminders while logged out. Graded by
planted state: the lines a stub notifier wrote per machine, claim files on disk, exact dates worked out by hand.

  evals/pa_devices.py              every case
  evals/pa_devices.py --only NAME  one of: once synced stale recurring pinned calendar grammar linger missed autoreply
Two machines are two processes with different SAKURA_PA_HOST values. They share one state directory, or each has its
own and `sync` below copies newer files across, the way a file sync would. Time is SAKURA_PA_NOW. No model, no network.
"""
import argparse
import glob
import importlib.machinery
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PA = os.path.join(HERE, "bin", "pa")


def pa_module():
    return importlib.machinery.SourceFileLoader("pa_mod", PA).load_module()


class Machine:
    """One computer: its name, its copy of the state directory, and a notifier that writes what it was told to a file."""

    def __init__(self, tmp, name, state=None, path=None, tag=None):
        tag = tag or name  # two copies of one machine, for what-if runs, keep their files apart by tag
        self.name, self.dir = name, state or os.path.join(tmp, "state-" + tag)
        self.heard_file = os.path.join(tmp, "heard-" + tag)
        stub = os.path.join(tmp, "notify-" + tag)
        with open(stub, "w") as f:
            f.write(f'#!/bin/sh\necho "$1|$2" >> {self.heard_file}\n')
        os.chmod(stub, 0o755)
        self.env = dict(os.environ, SAKURA_PA_DIR=self.dir, SAKURA_PA_HOST=name, SAKURA_PA_NO_TIMER="1", SAKURA_PA_NOTIFY=stub,
                        SAKURA_PA_LOCAL=os.path.join(tmp, "local-" + tag), TZ="UTC")
        if path:
            self.env["PATH"] = path + os.pathsep + self.env["PATH"]

    def pa(self, at, *args, **env):
        e = dict(self.env, SAKURA_PA_NOW=at, **env)
        r = subprocess.run([PA] + list(args), env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def heard(self, word):
        try:
            return open(self.heard_file).read().count(word)
        except OSError:
            return 0

    def schedule(self):
        try:
            return json.load(open(os.path.join(self.dir, "schedule.json")))
        except (OSError, ValueError):
            return []

    def claims(self):
        return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(self.dir, "claims", "*.json")))]


def sync(a, b):
    """What a file sync does between two copies: every file ends up as its newest version, and a deletion travels.
    The eval says which side deleted by passing it first: files only in `b` that `a` once had are gone from both."""
    for src, dst in ((a.dir, b.dir), (b.dir, a.dir)):
        for root, _, names in os.walk(src):
            for n in names:
                if n.startswith("."):
                    continue
                s = os.path.join(root, n)
                d = os.path.join(dst, os.path.relpath(s, src))
                if not os.path.exists(d) or os.stat(s).st_mtime_ns > os.stat(d).st_mtime_ns:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)


def once(tmp):
    """One shared directory, as on a network home: both machines tick in the same minute."""
    shared = os.path.join(tmp, "shared")
    a, b = Machine(tmp, "desk", shared), Machine(tmp, "lap", shared)
    a.pa("2026-11-11T08:00:00", "remind", "today", "10am", "call", "mum")
    b.pa("2026-11-11T08:05:00", "list")  # the laptop is known, and was used last
    a.pa("2026-11-11T09:59:00", "tick")
    b.pa("2026-11-11T09:59:00", "tick")
    early = a.heard("call mum") + b.heard("call mum")
    procs = [subprocess.Popen([PA, "tick"], env=dict(m.env, SAKURA_PA_NOW="2026-11-11T10:00:00")) for m in (a, b)]
    for p in procs:
        p.wait()
    for minute in ("10:01", "10:02", "10:03", "10:15"):
        a.pa(f"2026-11-11T{minute}:00", "tick")
        b.pa(f"2026-11-11T{minute}:00", "tick")
    fired = [c for c in a.claims() if c.get("fired")]
    code, listed = a.pa("2026-11-11T10:16:00", "list", "--fired")
    return {"nothing fires before it's due": early == 0,
            "two machines ticking at once: the reminder is heard exactly once": a.heard("call mum") + b.heard("call mum") == 1,
            "on the machine used last, not the one that made it": b.heard("call mum") == 1,
            "one claim on disk, naming that machine and the minute": len(fired) == 1 and fired[0]["host"] == "lap" and fired[0]["occ"] == "2026-11-11T10:00:00",
            "pa list --fired says where it fired": code == 0 and "on lap" in listed and "call mum" in listed,
            "the one-off is gone from the schedule": a.schedule() == []}


def synced(tmp):
    """Each machine has its own copy, and the sync runs between ticks."""
    a, b = Machine(tmp, "desk"), Machine(tmp, "lap")
    a.pa("2026-11-11T08:00:00", "remind", "today", "10am", "call", "mum")
    a.pa("2026-11-11T08:01:00", "tick")
    sync(a, b)
    b.pa("2026-11-11T08:02:00", "tick")
    sync(a, b)
    a.pa("2026-11-11T09:30:00", "list")  # the desk is where the user is
    sync(a, b)
    for m in (a, b):  # 10:00 on both, before anything has synced
        m.pa("2026-11-11T10:00:00", "tick")
    first = (a.heard("call mum"), b.heard("call mum"))
    b.pa("2026-11-11T10:01:00", "tick")
    waited = b.heard("call mum")
    sync(a, b)
    for minute in ("10:02", "10:03", "10:20", "11:00"):
        for m in (a, b):
            m.pa(f"2026-11-11T{minute}:00", "tick")
    res = {"the machine in use fires at the minute it's due": first == (1, 0),
           "the other waits its stagger rather than firing unsynced": waited == 0,
           "once the claim has synced it stands down for good": (a.heard("call mum"), b.heard("call mum")) == (1, 0),
           "and drops the item from its own copy": b.schedule() == []}
    # `pa set home` outranks who was used last.
    a.pa("2026-11-11T12:00:00", "set", "home", "lap")
    a.pa("2026-11-11T12:00:00", "remind", "today", "1pm", "water", "plants")
    a.pa("2026-11-11T12:30:00", "list")
    sync(a, b)
    for m in (a, b):
        m.pa("2026-11-11T13:00:00", "tick")
    res["pa set home HOST makes that machine the one that fires"] = (a.heard("water plants"), b.heard("water plants")) == (0, 1)
    sync(a, b)
    for m in (a, b):
        m.pa("2026-11-11T13:05:00", "tick")
    res["and still only once"] = a.heard("water plants") + b.heard("water plants") == 1
    # No sync at all: the second machine can't know, and a late duplicate beats a miss.
    c, d = Machine(tmp, "one"), Machine(tmp, "two")
    c.pa("2026-11-11T08:00:00", "remind", "today", "10am", "take", "pills")
    c.pa("2026-11-11T08:00:00", "tick")
    sync(c, d)
    d.pa("2026-11-11T08:01:00", "tick")
    sync(c, d)
    shutil.rmtree(c.dir)  # the first machine is off, or offline, when it comes due
    d.pa("2026-11-11T10:00:00", "tick")
    d.pa("2026-11-11T10:01:00", "tick")
    held = d.heard("take pills")
    d.pa("2026-11-11T10:02:00", "tick")
    res["with the first machine gone, the second fires after its stagger: late, not never"] = held == 0 and d.heard("take pills") == 1
    # A machine that was off while it came due waits one stagger for the sync before firing what it missed.
    e, f = Machine(tmp, "up"), Machine(tmp, "down")
    e.pa("2026-11-11T08:00:00", "remind", "today", "10am", "feed", "cat")
    e.pa("2026-11-11T08:00:00", "tick")
    sync(e, f)
    f.pa("2026-11-11T08:01:00", "tick")
    f.pa("2026-11-11T08:02:00", "list")  # used last, so it would go first
    sync(e, f)
    e.pa("2026-11-11T10:00:00", "tick")
    e.pa("2026-11-11T10:02:00", "tick")  # the one that's on fires after its stagger
    f.pa("2026-11-11T14:00:00", "tick")  # the other boots hours later with a stale copy
    woke = f.heard("feed cat")
    sync(e, f)
    f.pa("2026-11-11T14:02:00", "tick")
    f.pa("2026-11-11T14:10:00", "tick")
    res["a machine back from being off doesn't fire what another already did"] = e.heard("feed cat") == 1 and woke == 0 and f.heard("feed cat") == 0
    return res


def stale(tmp):
    a, b = Machine(tmp, "desk"), Machine(tmp, "lap")
    a.pa("2026-11-11T08:00:00", "remind", "today", "10am", "call", "mum")
    a.pa("2026-11-11T08:00:00", "tick")
    sync(a, b)
    b.pa("2026-11-11T08:01:00", "tick")
    a.pa("2026-11-11T09:00:00", "list")
    sync(a, b)
    # What the claim looks like at the moment of firing: this notifier copies it aside.
    seen, spy = os.path.join(tmp, "claim-at-firing"), os.path.join(tmp, "spy")
    with open(spy, "w") as f:
        f.write(f"#!/bin/sh\ncat {a.dir}/claims/*.json > {seen}\n")
    os.chmod(spy, 0o755)
    a.pa("2026-11-11T10:00:00", "tick", SAKURA_PA_NOTIFY=spy)
    during = json.load(open(seen)) if os.path.exists(seen) else {}
    after = a.claims()
    # Now what a crash between the claim and the firing leaves behind: the claim, unfired, and the item already off the schedule.
    for c in after:
        json.dump(dict(c, fired=None), open(os.path.join(a.dir, "claims", f"{c['id']}@20261111T100000.desk.json"), "w"))
    kept = json.load(open(os.path.join(b.dir, "schedule.json")))
    sync(a, b)
    # First, a laptop whose schedule still has the item (the claim arrived before the schedule did).
    c = Machine(tmp, "lap", tag="lap-behind")
    shutil.copytree(b.dir, c.dir)
    shutil.copytree(b.env["SAKURA_PA_LOCAL"], c.env["SAKURA_PA_LOCAL"])
    json.dump(kept, open(os.path.join(c.dir, "schedule.json"), "w"))
    for minute in ("10:02", "10:05", "10:09"):
        c.pa(f"2026-11-11T{minute}:00", "tick")
    behind_waits = c.heard("call mum")
    c.pa("2026-11-11T10:10:00", "tick")
    behind_fires = c.heard("call mum")
    # Then one whose schedule has already lost it: all it has is the claim.
    for minute in ("10:02", "10:05", "10:09"):
        b.pa(f"2026-11-11T{minute}:00", "tick")
    fresh = b.heard("call mum")
    b.pa("2026-11-11T10:11:00", "tick")  # stale from 10:10, but the laptop is second in turn: 10:12
    early = b.heard("call mum")
    b.pa("2026-11-11T10:12:00", "tick")
    taken = b.heard("call mum")
    b.pa("2026-11-11T10:13:00", "tick")
    b.pa("2026-11-11T10:30:00", "tick")
    sync(a, b)
    a.pa("2026-11-11T10:31:00", "tick")
    a.pa("2026-11-11T10:45:00", "tick")
    mine = [x for x in b.claims() if x["host"] == "lap"]
    return {"the claim is on disk, unfired, before the notification goes out": during.get("host") == "desk" and during.get("fired", 0) is None and during.get("occ") == "2026-11-11T10:00:00",
            "and is marked fired after": len(after) == 1 and after[0]["fired"] == "2026-11-11T10:00:00",
            "a fresh claim by another machine is left alone, though the item is due here": behind_waits == 0,
            "once it's ten minutes old and still unfired, the item fires here": behind_fires == 1,
            "with the item gone from the schedule, a fresh claim is left alone too": fresh == 0,
            "the takeover waits for this machine's turn": early == 0 and taken == 1,
            "exactly once": b.heard("call mum") == 1,
            "the takeover is its own claim, fired, and says it was late": len(mine) == 1 and mine[0]["fired"] == "2026-11-11T10:12:00" and "was due 2026-11-11 10:00" in open(b.heard_file).read(),
            "the machine that dropped it doesn't fire it again": not os.path.exists(a.heard_file)}


def recurring(tmp):
    a, b = Machine(tmp, "desk"), Machine(tmp, "lap")
    a.pa("2026-11-11T08:00:00", "remind", "every", "day", "9am", "stand", "up")
    a.pa("2026-11-11T08:00:00", "tick")
    sync(a, b)
    b.pa("2026-11-11T08:01:00", "tick")
    a.pa("2026-11-11T08:30:00", "list")
    sync(a, b)
    counts = []
    for m in (a, b):  # the 11th's own 09:00 is still ahead; both machines stay on through it
        for minute in ("08:52", "09:00", "09:01"):
            m.pa(f"2026-11-11T{minute}:00", "tick")
    sync(a, b)
    for m in (a, b):
        m.pa("2026-11-11T09:02:00", "tick")
    sync(a, b)
    first_day = a.heard("stand up") + b.heard("stand up")
    for day in ("12", "13", "14"):
        for minute in ("08:52", "09:00", "09:01"):
            for m in (a, b):
                m.pa(f"2026-11-{day}T{minute}:00", "tick")
        sync(a, b)
        for minute in ("09:02", "09:03", "09:30"):
            for m in (a, b):
                m.pa(f"2026-11-{day}T{minute}:00", "tick")
        sync(a, b)
        counts.append(a.heard("stand up") + b.heard("stand up"))
    occs = sorted(c["occ"] for c in a.claims() if c.get("fired"))
    same = a.schedule() == b.schedule() and len(a.schedule()) == 1 and a.schedule()[0]["at"] == "2026-11-15T09:00:00"
    code, listed = b.pa("2026-11-14T10:00:00", "list")
    # The laptop's copy never gets the desk's schedule.json, only its claims: it must move on by the claim's own next time.
    c, d = Machine(tmp, "one"), Machine(tmp, "two")
    c.pa("2026-11-11T08:00:00", "remind", "every", "2", "hours", "stretch")
    c.pa("2026-11-11T08:00:00", "tick")
    sync(c, d)
    d.pa("2026-11-11T08:01:00", "tick")
    c.pa("2026-11-11T08:02:00", "list")
    c.pa("2026-11-11T10:07:00", "tick")  # late by seven minutes: the next one is 12:07 on this machine
    shutil.copytree(os.path.join(c.dir, "claims"), os.path.join(d.dir, "claims"), dirs_exist_ok=True)
    d.pa("2026-11-11T10:09:00", "tick")
    return {"a daily reminder on two machines is heard once a day, four days running": [first_day] + counts == [1, 2, 3, 4],
            "each occurrence has its own claim": occs == ["2026-11-11T09:00:00", "2026-11-12T09:00:00", "2026-11-13T09:00:00", "2026-11-14T09:00:00"],
            "both copies of the schedule end up identical, on the next occurrence": same,
            "pa list says where it last fired": code == 0 and "last fired on desk, 11-14 09:00" in listed,
            "a machine that only sees the claim adopts the claimer's next time": d.heard("stretch") == 0 and d.schedule()[0]["at"] == "2026-11-11T12:07:00" == c.schedule()[0]["at"]}


def pinned(tmp):
    a, b = Machine(tmp, "desk"), Machine(tmp, "lap")
    mark = os.path.join(tmp, "ran")
    subprocess.run([PA, "cron", "today 10:00", "--", f"echo $SAKURA_PA_HOST >> {mark}"], env=dict(a.env, SAKURA_PA_NOW="2026-11-11T08:00:00"), cwd=tmp, capture_output=True)
    a.pa("2026-11-11T08:00:00", "remind", "today", "11am", "pinned", "thing")
    rid = next(i["id"] for i in a.schedule() if i["kind"] == "reminder")
    code, said = a.pa("2026-11-11T08:00:00", "pin", rid, "lap")
    a.pa("2026-11-11T08:00:00", "tick")
    sync(a, b)
    b.pa("2026-11-11T08:01:00", "tick")
    b.pa("2026-11-11T08:02:00", "list")  # the laptop is used last, so it would go first for anything unpinned
    sync(a, b)
    for minute in ("10:00", "10:05", "10:30"):
        b.pa(f"2026-11-11T{minute}:00", "tick")
    not_here = not os.path.exists(mark)
    a.pa("2026-11-11T10:31:00", "tick")
    for minute in ("11:00", "11:05", "11:30"):
        a.pa(f"2026-11-11T{minute}:00", "tick")
    held = a.heard("pinned thing")
    b.pa("2026-11-11T11:31:00", "tick")
    # Cancelled on one machine while the other's copy still has it: the cancel travels as a file, not as a missing line.
    a.pa("2026-11-11T12:00:00", "remind", "today", "3pm", "cancelled", "thing")
    sync(a, b)
    cid = next(i["id"] for i in a.schedule() if i.get("text") == "cancelled thing")
    a.pa("2026-11-11T12:10:00", "cancel", cid)
    shutil.copytree(os.path.join(a.dir, "claims"), os.path.join(b.dir, "claims"), dirs_exist_ok=True)
    b.pa("2026-11-11T15:00:00", "tick")
    b.pa("2026-11-11T15:10:00", "tick")
    # A sync that couldn't merge leaves the other copy beside the schedule: nothing in it is lost.
    a.pa("2026-11-11T16:00:00", "remind", "today", "5pm", "mine")
    other = [dict(a.schedule()[-1], id="zzzzzz", text="theirs", at="2026-11-11T17:00:00")]
    json.dump(other, open(os.path.join(a.dir, "schedule.sync-conflict-20261111-160000-ABCDEFG.json"), "w"))
    a.pa("2026-11-11T17:00:00", "tick")
    return {"a cron command is pinned to the machine that made it": a.schedule() == [] or all(i.get("pin") == "desk" for i in json.load(open(os.path.join(b.dir, "schedule.json"))) if i["kind"] == "command") and not_here,
            "another machine never runs it, however long it waits": not_here,
            "its own machine runs it once": open(mark).read().split() == ["desk"],
            "pa pin ID HOST holds a reminder for that machine": code == 0 and held == 0 and b.heard("pinned thing") == 1,
            "a cancel reaches a machine whose schedule still had the item": b.heard("cancelled thing") == 0 and not any(i.get("text") == "cancelled thing" for i in b.schedule()),
            "a sync-conflict copy of the schedule is merged, not ignored": a.heard("mine") == 1 and a.heard("theirs") == 1 and not glob.glob(os.path.join(a.dir, "*conflict*"))}


ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:weekly@x
DTSTART;TZID=Europe/Berlin:20261005T090000
DTEND;TZID=Europe/Berlin:20261005T100000
RRULE:FREQ=WEEKLY;BYDAY=MO
EXDATE;TZID=Europe/Berlin:20261109T090000
SUMMARY:Team sync
BEGIN:VALARM
TRIGGER:-PT10M
DESCRIPTION:not an event
END:VALARM
END:VEVENT
BEGIN:VEVENT
UID:standup@x
DTSTART:20261102T083000Z
RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20261113T083000Z
SUMMARY:Standup\\, short
END:VEVENT
BEGIN:VEVENT
UID:rent@x
DTSTART;VALUE=DATE:20260101
RRULE:FREQ=MONTHLY;BYMONTHDAY=1
SUMMARY:Rent due
END:VEVENT
BEGIN:VEVENT
UID:lastfri@x
DTSTART:20260130T160000
RRULE:FREQ=MONTHLY;BYDAY=-1FR
SUMMARY:Retro
END:VEVENT
BEGIN:VEVENT
UID:bday@x
DTSTART;VALUE=DATE:19900312
RRULE:FREQ=YEARLY
SUMMARY:Asha's birthday
END:VEVENT
BEGIN:VEVENT
UID:gym@x
DTSTART:20261103T180000
RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH;COUNT=5
SUMMARY:Gym
END:VEVENT
BEGIN:VEVENT
UID:moved@x
DTSTART:20261104T140000
RRULE:FREQ=WEEKLY
SUMMARY:One to one
END:VEVENT
BEGIN:VEVENT
UID:moved@x
RECURRENCE-ID:20261118T140000
DTSTART:20261119T110000
SUMMARY:One to one (moved)
END:VEVENT
BEGIN:VEVENT
UID:single@x
DTSTART:20261116T120000
SUMMARY:Lunch with Ravi
END:VEVENT
BEGIN:VEVENT
UID:nyc@x
DTSTART;TZID=America/New_York:20260301T200000
RRULE:FREQ=WEEKLY;BYDAY=SU
SUMMARY:Call home
END:VEVENT
BEGIN:VEVENT
UID:conf@x
DTSTART;VALUE=DATE:20261123
DTEND;VALUE=DATE:20261126
SUMMARY:Conference
END:VEVENT
BEGIN:VEVENT
UID:setpos@x
DTSTART:20260130T170000
RRULE:FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1
SUMMARY:Invoices
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")


def calendar(tmp):
    """Every date here is worked out by hand from a 2026 calendar; none comes from the code under test."""
    p = pa_module()
    f = os.path.join(tmp, "work.ics")
    with open(f, "w", newline="") as fh:
        fh.write(ICS)

    def on(day, tz="UTC"):
        # zoneinfo only: the brief is a subprocess, so TZ is the reader's zone
        m = Machine(tmp, "cal-" + tz.replace("/", "-"))
        m.env["TZ"] = tz
        m.pa(f"{day}T07:00:00", "set", "calendar", f)
        code, out = m.pa(f"{day}T07:00:00", "brief", "everyone")
        block = out.split("\nCalendar\n", 1)[1].split("\n\n", 1)[0] if "\nCalendar\n" in out else ""
        return [line.strip() for line in block.splitlines() if line.strip()]

    res = {}
    # Berlin leaves summer time on 25 October 2026: 09:00 there is 07:00 UTC before it and 08:00 UTC after.
    res["a weekly meeting shows in today's brief (Monday 19 Oct, 09:00 Berlin = 07:00 UTC)"] = "07:00 Team sync" in on("2026-10-19")
    res["and keeps its wall-clock hour across the DST change (Monday 26 Oct = 08:00 UTC)"] = "08:00 Team sync" in on("2026-10-26")
    res["in the reader's own zone (Kathmandu, +5:45: 12:45 then 13:45)"] = "12:45 Team sync" in on("2026-10-19", "Asia/Kathmandu") and "13:45 Team sync" in on("2026-10-26", "Asia/Kathmandu")
    res["not on a day it doesn't fall (Tuesday 20 Oct)"] = not any("Team sync" in e for e in on("2026-10-20"))
    res["an EXDATE removes that one instance (9 Nov) and not the next (16 Nov)"] = not any("Team sync" in e for e in on("2026-11-09")) and "08:00 Team sync" in on("2026-11-16")
    res["a VALARM inside the event isn't read as the event"] = not any("not an event" in e for d in ("2026-10-19", "2026-11-16") for e in on(d))
    res["DAILY with BYDAY skips Saturday 7 Nov"] = "08:30 Standup, short" in on("2026-11-06") and not any("Standup" in e for e in on("2026-11-07"))
    res["UNTIL includes its last day (Fri 13 Nov) and ends there (Mon 16 Nov)"] = "08:30 Standup, short" in on("2026-11-13") and not any("Standup" in e for e in on("2026-11-16"))
    res["an all-day monthly event on the 1st (BYMONTHDAY)"] = "Rent due" in on("2026-12-01") and "Rent due" not in on("2026-12-02")
    res["the last Friday of the month (BYDAY=-1FR): 27 Nov, not 20 Nov"] = "16:00 Retro" in on("2026-11-27") and not any("Retro" in e for e in on("2026-11-20"))
    res["a yearly birthday from 1990"] = "Asha's birthday" in on("2027-03-12") and "Asha's birthday" not in on("2027-03-11")
    # Gym: every second week on Tue and Thu from Tue 3 Nov, five times: 3, 5, 17, 19 Nov and 1 Dec.
    gym = {d: any("Gym" in e for e in on(d)) for d in ("2026-11-03", "2026-11-05", "2026-11-10", "2026-11-17", "2026-11-19", "2026-12-01", "2026-12-03", "2026-12-15")}
    res["INTERVAL=2 skips the off week, and COUNT=5 ends it on 1 Dec"] = gym == {"2026-11-03": True, "2026-11-05": True, "2026-11-10": False, "2026-11-17": True, "2026-11-19": True, "2026-12-01": True, "2026-12-03": False, "2026-12-15": False}
    res["a moved instance (RECURRENCE-ID) shows on its new day only"] = not any("One to one" in e for e in on("2026-11-18")) and on("2026-11-19").count("11:00 One to one (moved)") == 1 and "14:00 One to one" in on("2026-11-25")
    res["a single event still works"] = "12:00 Lunch with Ravi" in on("2026-11-16")
    # New York, Sundays 20:00. 1 March is EST (01:00 UTC Monday); from 8 March it's EDT (00:00 UTC Monday).
    res["an evening event lands on the next day for a reader ahead of it, across the US DST start"] = "01:00 Call home" in on("2026-03-02") and "00:00 Call home" in on("2026-03-09") and not any("Call home" in e for e in on("2026-03-08"))
    res["a three-day all-day event covers each day and not the fourth"] = all("Conference" in on(d) for d in ("2026-11-23", "2026-11-24", "2026-11-25")) and "Conference" not in on("2026-11-26")
    res["the last weekday of the month (BYSETPOS=-1): Fri 30 Oct and Mon 30 Nov"] = "17:00 Invoices" in on("2026-10-30") and "17:00 Invoices" in on("2026-11-30") and not any("Invoices" in e for e in on("2026-10-31"))
    res["a leap-day yearly rule skips plain years"] = [t.year for t in p._recur(datetime(2024, 2, 29, 9), {"FREQ": "YEARLY"}, datetime(2033, 1, 1))] == [2024, 2028, 2032]
    return res


def grammar(tmp):
    p = pa_module()
    base = datetime(2026, 11, 11, 10, 0)  # a Wednesday
    res = {}
    for text, first, later, what in (
        ("every month on the 1st 9am pay rent", "2026-12-01 09:00", ["2027-01-01 09:00", "2027-02-01 09:00"], "pay rent"),
        ("every month on the 31st 8am backups", "2026-11-30 08:00", ["2026-12-31 08:00", "2027-01-31 08:00", "2027-02-28 08:00"], "backups"),
        ("every month on the last day at 18:00 close the books", "2026-11-30 18:00", ["2026-12-31 18:00", "2027-01-31 18:00"], "close the books"),
        ("every 3 months on the 15th 8am file VAT", "2026-11-15 08:00", ["2027-02-15 08:00", "2027-05-15 08:00"], "file VAT"),
        ("every year dec 26 9am boxing day call", "2026-12-26 09:00", ["2027-12-26 09:00"], "boxing day call"),
        ("every year on 26 dec at 9am boxing day call", "2026-12-26 09:00", ["2027-12-26 09:00"], "boxing day call"),
        ("every mar 12 asha's birthday", "2027-03-12 09:00", ["2028-03-12 09:00"], "asha's birthday"),
        ("every feb 29 7am leap", "2027-02-28 07:00", ["2028-02-29 07:00", "2029-02-28 07:00"], "leap"),
        ("every weekday 9am standup", "2026-11-12 09:00", ["2026-11-13 09:00", "2026-11-16 09:00"], "standup"),
        ("every 2 weeks friday 3pm retro", "2026-11-13 15:00", ["2026-11-27 15:00", "2026-12-11 15:00"], "retro"),
        ("every other week on mon 10:30 planning", "2026-11-16 10:30", ["2026-11-30 10:30"], "planning"),
        ("every 2 days 8am water the plants", "2026-11-13 08:00", ["2026-11-15 08:00", "2026-11-17 08:00"], "water the plants"),
        ("every monday 9am review", "2026-11-16 09:00", ["2026-11-23 09:00"], "review"),
    ):
        label = f"repeat: {text}"
        try:
            at, rule, w = p.parse_reminder(text, base)
            got, t = [], at
            for _ in later:
                t = p.next_run(rule, t)
                got.append(t.strftime("%Y-%m-%d %H:%M"))
            res[label] = at.strftime("%Y-%m-%d %H:%M") == first and got == later and w == what
            if not res[label]:
                print("   got", at, got, repr(w))
        except Exception as e:
            res[label] = False
            print("   ", text, e)
    # A late firing mustn't knock a stepped rule off its days: fired on Saturday instead of Friday, the next is still Friday week.
    _, rule, _ = p.parse_reminder("every 2 weeks friday 3pm retro", base)
    res["a fortnightly reminder fired a day late keeps its Fridays"] = p.next_run(rule, datetime(2026, 11, 14, 8, 0)) == datetime(2026, 11, 27, 15, 0)
    first, rule, _ = p.parse_reminder("every week 9am bins", base)  # 09:00 has passed, so the first is Wednesday 18 Nov
    res["a weekly one fired two days late keeps its weekday"] = first == datetime(2026, 11, 18, 9, 0) and p.next_run(rule, datetime(2026, 11, 20, 12, 0)) == datetime(2026, 11, 25, 9, 0)
    _, rule, _ = p.parse_reminder("every 2 days 8am water", base)
    res["an every-2-days one fired a day late keeps its days"] = p.next_run(rule, datetime(2026, 11, 14, 12, 0)) == datetime(2026, 11, 15, 8, 0)
    # Weekdays and dates count from the given moment, not from the clock on the wall of the machine running this.
    far = datetime(2031, 3, 5, 12, 0)  # a Wednesday
    res["'monday 3pm' counts from the asked moment, not today's date"] = p.parse_reminder("monday 3pm dentist", far)[0] == datetime(2031, 3, 10, 15, 0)
    res["so does 'dec 26 9am'"] = p.parse_reminder("dec 26 9am gifts", far)[0] == datetime(2031, 12, 26, 9, 0)
    for text in ("every 26 bottles of beer", "every month on the 45th x", "every feb 31 x"):
        try:
            p.parse_reminder(text, base)
            res[f"refuses: {text}"] = False
        except ValueError:
            res[f"refuses: {text}"] = True
    m = Machine(tmp, "g")
    code, out = m.pa("2026-11-11T10:00:00", "remind", "every", "month", "on", "the", "1st", "9am", "pay", "rent")
    code2, listed = m.pa("2026-11-11T10:00:00", "list")
    res["pa list describes it in words"] = code == 0 and "every month on the 1st at 09:00, next 2026-12-01 09:00  pay rent" in listed
    m.pa("2026-12-01T09:00:00", "tick")
    m.pa("2027-01-03T12:00:00", "tick")
    res["and it fires once a month, the missed one late"] = m.heard("pay rent") == 2 and m.schedule()[0]["at"] == "2027-02-01T09:00:00"
    return res


def linger(tmp):
    fake = os.path.join(tmp, "fakebin")
    os.makedirs(fake)
    state, calls = os.path.join(tmp, "linger-state"), os.path.join(tmp, "calls")
    with open(os.path.join(fake, "loginctl"), "w") as f:
        f.write(f"""#!/bin/sh
echo "loginctl $*" >> {calls}
case "$1" in
  show-user) [ -e {state}.unknown ] && {{ echo "Failed to get user: not logged in or lingering" >&2; exit 1; }}; echo "Linger=$(cat {state})";;
  enable-linger) [ -e {state}.denied ] && {{ echo "Access denied" >&2; exit 1; }}; echo yes > {state};;
  disable-linger) echo no > {state};;
esac
""")
    with open(os.path.join(fake, "systemctl"), "w") as f:
        f.write(f'#!/bin/sh\necho "systemctl $*" >> {calls}\n[ "$2" = is-enabled ] && echo enabled\nexit 0\n')
    with open(os.path.join(fake, "sudo"), "w") as f:
        f.write(f'#!/bin/sh\necho "sudo $*" >> {calls}\nexit 1\n')
    for n in ("loginctl", "systemctl", "sudo"):
        os.chmod(os.path.join(fake, n), 0o755)
    m = Machine(tmp, "box", path=fake)
    m.env.update(USER="asha", XDG_CONFIG_HOME=os.path.join(tmp, "conf"), SAKURA_PA_LINGER_DIR=os.path.join(tmp, "marks"))
    open(state, "w").write("no\n")
    res = {}
    code, out = m.pa("2026-11-11T08:00:00", "linger")
    res["pa linger sees lingering is off, and exits 1"] = code == 1 and "pa linger on" in out
    m.pa("2026-11-11T08:00:00", "remind", "today", "10am", "x")
    code, out = m.pa("2026-11-11T08:00:00", "list")
    res["pa list says reminders stop at logout, with the fix"] = "stops checking when you log out" in out and "pa linger on" in out
    code, out = m.pa("2026-11-11T08:00:00", "devices")
    res["pa devices says so too"] = "STOPS firing" in out
    open(state + ".denied", "w").close()
    code, out = m.pa("2026-11-11T08:00:00", "linger", "on")
    res["a refused enable-linger is reported as not done, with the root command"] = code != 0 and "loginctl enable-linger asha" in out and open(state).read().strip() == "no" and "sudo -A loginctl enable-linger asha" in open(calls).read()
    os.remove(state + ".denied")
    code, out = m.pa("2026-11-11T08:00:00", "linger", "on")
    res["pa linger on runs loginctl enable-linger for this user"] = code == 0 and "loginctl enable-linger asha" in open(calls).read() and open(state).read().strip() == "yes"
    code, out = m.pa("2026-11-11T08:00:00", "linger")
    res["then pa linger exits 0"] = code == 0
    code, out = m.pa("2026-11-11T08:00:00", "list")
    res["and pa list stops mentioning it"] = "log out" not in out
    # No session at all (asked from cron or ssh with no logind session): the marker file is the answer.
    open(state + ".unknown", "w").close()
    os.makedirs(os.path.join(tmp, "marks"))
    code, _ = m.pa("2026-11-11T08:00:00", "linger")
    open(os.path.join(tmp, "marks", "asha"), "w").close()
    code2, _ = m.pa("2026-11-11T08:00:00", "linger")
    res["with no session to ask, the linger marker file decides"] = (code, code2) == (1, 0)
    os.remove(state + ".unknown")
    # The real install path: the first reminder writes the units, and says so when lingering is off.
    open(state, "w").write("no\n")
    env = {k: v for k, v in m.env.items() if k != "SAKURA_PA_NO_TIMER"}
    r = subprocess.run([PA, "remind", "tomorrow", "10am", "y"], env=dict(env, SAKURA_PA_NOW="2026-11-11T08:00:00"), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    units = os.path.join(tmp, "conf", "systemd", "user")
    timer = open(os.path.join(units, "sakura-pa.timer")).read() if os.path.exists(os.path.join(units, "sakura-pa.timer")) else ""
    res["the timer it installs is Persistent, so a run missed while off happens at boot"] = "Persistent=true" in timer and "OnCalendar=minutely" in timer and "systemctl --user enable --now sakura-pa.timer" in open(calls).read()
    res["installing the timer warns when it won't survive logout"] = "pa linger on" in r.stderr
    return res


def missed(tmp):
    """Off, or logged out without lingering: nothing ticks. Everything that came due fires at the first tick back."""
    m = Machine(tmp, "solo")
    mark = os.path.join(tmp, "ran")
    m.pa("2026-11-11T08:00:00", "remind", "today", "10am", "call", "mum")
    m.pa("2026-11-11T08:00:00", "remind", "today", "11am", "pay", "bill")
    m.pa("2026-11-11T08:00:00", "remind", "every", "day", "9am", "stand", "up")
    subprocess.run([PA, "cron", "today 12:00", "--", f"echo ran >> {mark}"], env=dict(m.env, SAKURA_PA_NOW="2026-11-11T08:00:00"), cwd=tmp, capture_output=True)
    m.pa("2026-11-11T08:01:00", "tick")
    m.pa("2026-11-14T07:30:00", "tick")  # three days later
    heard = open(m.heard_file).read() if os.path.exists(m.heard_file) else ""
    code, pending = m.pa("2026-11-14T07:31:00", "pending")
    m.pa("2026-11-14T07:32:00", "tick")
    return {"both one-offs missed while off fire at the first tick back": m.heard("call mum") == 1 and m.heard("pay bill") == 1,
            "each says when it was due": "call mum (was due 2026-11-11 10:00)" in heard and "pay bill (was due 2026-11-11 11:00)" in heard,
            "a daily reminder missed three times fires once, not three times": m.heard("stand up") == 1,
            "and is set for the next morning it hasn't missed": [i["at"] for i in m.schedule() if i.get("rule")] == ["2026-11-14T09:00:00"],
            "a missed command runs once": os.path.exists(mark) and open(mark).read().split() == ["ran"],
            "the next shell shows what was missed": "call mum" in pending and "pay bill" in pending,
            "nothing fires twice on the tick after": m.heard("call mum") == 1 and m.heard("stand up") == 1,
            "on one machine nothing waits for a stagger": json.load(open(glob.glob(os.path.join(m.dir, "claims", "*.solo.json"))[0]))["fired"] == "2026-11-14T07:30:00"}


def autoreply(tmp):
    """Two machines, one mailbox: a stand-in himalaya records every send. One reply, not two."""
    fake = os.path.join(tmp, "fakebin")
    os.makedirs(fake)
    sent, arrived = os.path.join(tmp, "sent"), os.path.join(tmp, "arrived")
    with open(os.path.join(fake, "himalaya"), "w") as f:
        f.write(f"""#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
if a[:2] == ["envelope", "list"]:
    mail = {{"id": "7", "message-id": "<m7@x>", "date": "2026-11-11T09:05:00", "from": {{"email": "alice@x.test"}}, "subject": "Lunch?", "flags": []}}
    print(json.dumps([mail] if os.path.exists({arrived!r}) else []))
elif a[:2] == ["message", "read"]:
    print("From: alice@x.test\\nTo: me@x.test\\nSubject: Lunch?\\n\\nhello")
elif a[:2] == ["message", "send"]:
    open({sent!r}, "a").write(os.environ["SAKURA_PA_HOST"] + "\\n")
""")
    os.chmod(os.path.join(fake, "himalaya"), 0o755)
    conf = os.path.join(tmp, "conf", "himalaya")
    os.makedirs(conf)
    with open(os.path.join(conf, "config.toml"), "w") as f:
        f.write('[accounts.me]\ndefault = true\nemail = "me@x.test"\n')
    a, b = Machine(tmp, "desk", path=fake), Machine(tmp, "lap", path=fake)
    for m in (a, b):
        m.env["XDG_CONFIG_HOME"] = os.path.join(tmp, "conf")
    a.pa("2026-11-11T09:00:00", "autoreply", "on", "Away today.")
    a.pa("2026-11-11T09:00:00", "tick")
    sync(a, b)
    b.pa("2026-11-11T09:01:00", "tick")
    a.pa("2026-11-11T09:02:00", "list")
    sync(a, b)
    open(arrived, "w").close()  # the mail comes in at 09:05
    senders = lambda: open(sent).read().split() if os.path.exists(sent) else []
    # From here each machine keeps its own autoreply.json (the worst case: that file is slow to sync); only autoreply-by/ travels.
    for minute in ("09:09", "09:10", "09:11"):
        for m in (a, b):
            m.pa(f"2026-11-11T{minute}:00", "tick")
    first = senders()
    if os.path.isdir(os.path.join(a.dir, "autoreply-by")):
        shutil.copytree(os.path.join(a.dir, "autoreply-by"), os.path.join(b.dir, "autoreply-by"), dirs_exist_ok=True)
    for minute in ("09:12", "09:13", "09:15", "09:19"):
        for m in (a, b):
            m.pa(f"2026-11-11T{minute}:00", "tick")
    res = {"the machine in use answers the new mail, ten minutes after it last looked": first == ["desk"],
           "the other, seeing that it looked, sends nothing": senders() == ["desk"]}
    # With the first machine silent, the second looks after its stagger.
    c, d = Machine(tmp, "one", path=fake), Machine(tmp, "two", path=fake)
    os.remove(arrived)
    for m in (c, d):
        m.env["XDG_CONFIG_HOME"] = os.path.join(tmp, "conf")
    c.pa("2026-11-11T09:00:00", "autoreply", "on", "Away today.")
    c.pa("2026-11-11T09:00:00", "tick")
    sync(c, d)
    d.pa("2026-11-11T09:01:00", "tick")
    c.pa("2026-11-11T09:02:00", "list")
    sync(c, d)
    open(arrived, "w").close()
    for minute in ("09:10", "09:11"):
        d.pa(f"2026-11-11T{minute}:00", "tick")
    held = senders()
    d.pa("2026-11-11T09:12:00", "tick")
    res["with the first machine silent, the second answers after its stagger"] = held == ["desk"] and senders() == ["desk", "two"]
    return res


CASES = {"once": once, "synced": synced, "stale": stale, "recurring": recurring, "pinned": pinned, "calendar": calendar,
         "grammar": grammar, "linger": linger, "missed": missed, "autoreply": autoreply}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    total = passed = 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        with tempfile.TemporaryDirectory(prefix="sakura-pa-devices-") as tmp:
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
