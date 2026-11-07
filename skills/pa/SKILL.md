---
name: pa
description: Act as the user's personal assistant, for any role: reminders, schedules, briefings, standups, deadlines, time tracking, watching for changes, auto-replies
---

Use `pa` for all of this. It works without the model, survives reboots, and catches up on anything missed. Don't write cron jobs or reminder scripts. `pa --help` has the details.

Do what's asked, then say in a line or two what you set up and how to undo it (`pa cancel ID`, `pa autoreply off`). If the user's role is clear and not set, set it: `pa set role NAME`.

## Everyone
- "Remind me...": `pa remind tomorrow, 10am birthday wish`. If it has no clear time, ask for one rather than guessing.
- "What's on my plate?": `pa brief`.
- Deadlines: `pa todo add "thesis draft due:2026-12-01"`. They appear in the brief as they get close.
- News on a topic: `pa set topic "Nepal budget"`. Weather: `pa set place Kathmandu`.
- A calendar: `pa set calendar ~/cal/work.ics`. Single events only: it doesn't expand repeating ones yet.
- Tell me when something changes: `pa watch every day 8am: fx USD NPR`, with any `live` command.
- A job for later: `pa job every friday 5pm: summarise what changed in ~/notes this week`. It runs as a sandboxed worker with the network on, writing only to its own directory (not your files), so it can't send mail or push, and the result arrives as a notification.

## Away from email
For anything like "reply to all my mail": `pa autoreply on "message" --days 5`, not `pa job`, which can't send mail. Use the user's wording. If they say to make something up, use something plain and harmless, not a false claim about an illness, a death or an emergency. It only answers new mail, skips lists and automated senders, and replies to each person at most once a week. `pa autoreply preview` shows what it would do without sending. `pa autoreply off` stops it.

## Developer: `pa set role developer`, `pa set repo ~/code/app`
- `pa brief developer`: unpushed work, reviews waiting, failed builds, dependencies with known holes.
- `pa standup` from the git log and `pa log`.
- `pa watch every day 9am: releases laravel/framework`, and `pa watch every day 9am: vuln npm lodash 4.17.21`.
- `pa job every weekday 8am: review the open dependabot PRs in ~/code/app and tell me which are safe to merge`.

## Sysadmin: `pa set role sysadmin`, `pa set host example.com`
`pa brief sysadmin`: full disks, failed services, security updates, reboots needed, unhealthy containers, certificates ending soon, an OS past end of life. Fixing is separate: report first unless asked.

## Security: `pa set role security`, `pa set product "apache struts"`
`pa brief security`: what's being exploited in those products, vulnerable dependencies, certificates. `pa watch every day 8am: cve openssl`.

## Manager: `pa set role manager`
`pa brief manager`: PRs going quiet, reviews waiting on them, where the time went. Add 1:1 prep with `pa todo add "ask about the migration due:2026-11-10"`.

## Student: `pa set role student`, `pa set topic "..."`
Deadlines as to-dos with due dates, classes from a calendar, papers on their topics. `pa remind every sunday 6pm plan the week`.

## Researcher: `pa set role researcher`, `pa set topic "..."`
New papers and news on their topics. `pa watch every monday 8am: papers model quantization`. `rag` searches their own papers.

## Writer: `pa set role writer`, `pa set drafts ~/writing`
Words written today, per folder. `pa remind every day 9am write 500 words`.

## Freelancer: `pa set role freelancer`
`pa clock in client-a`, `pa clock out`, `pa clock report`. Invoices as to-dos: `pa todo add "invoice client-a due:2026-11-30"`. `pa watch every day 9am: fx USD NPR`.
