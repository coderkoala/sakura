# Roadmap

**The goal:** the thing people use once and say "I wish I had that 10 years ago." A senior colleague who lives in your terminal, knows your machines and your history, does the work and proves it, and never sends a word of it to anyone else.

## What must always be true

- **Yours.** Runs on your hardware. No account, no telemetry, no third party handling your work. Anything that leaves the machine is a request you asked for, to the source you asked.
- **Proven, not claimed.** It's done when a check says so, not when the model says so. Every feature has an eval graded by something other than the model.
- **Human work stays human.** CAPTCHAs, passwords and sends you asked to see first come to you. A site's refusal is final: no stealth, no solving, no disguise.
- **Mechanics over prompts.** When the model gets something wrong repeatedly, change what's possible, not what it's asked to do.

## Where it stands

Measured on one machine with an 8 GB GPU. Results vary between runs, so treat them as rates, not guarantees.

| Works, with an eval | Built, not proven enough |
|---|---|
| Multi-step work over ssh, with honest failure | Email with a real provider (tested on a local server only) |
| Live facts from primary sources | CAPTCHA hand-off on a real site (tested on a local page) |
| Disposable workers and a coordinator | Guards on the main agent (pattern matching, not a sandbox) |
| Long tasks that used to crash a 32k context | Tools it grows itself (a weak check can pass a weak tool) |
| Local document search, office files, the shared browser | Anything on a second machine, or on real 6 GB hardware |
| Reminders, briefs, watches, auto-reply | Workers with `network: yes` (keys, agents and sockets hidden unless the job names them) |
| A sandbox around workers: no network, writes only where the job allows | |
| `?fix`, `?undo`, `?recap` | `?tonight` on a real night's queue (the eval runs one) |
| `?tour` (9/9), `?tonight` (11/11) | `?teach` (1/3: it writes the script, then stops before `sakura-tool keep`) and `?learn` (no eval: nothing but a reader can grade a lesson) |
| The guardian's checks (deterministic) | The guardian's disk projection, until it has a fortnight of samples |

## Next: make what exists trustworthy

1. **Run evals in a disposable machine.** They run on the real host with sudo today, and have left containers and packages behind.
2. **Real-world passes.** A real mail provider, including OAuth for those that require it. A real CAPTCHA in the visible window. A second device end to end.
3. **`pa` across devices.** Reminders that follow you, firing once, not on all seven. Repeating calendar events. Reminders that work while logged out.
4. **Runs in more places.** A build for older glibc and for ARM, and a real run on a 6 GB card.
5. **Fewer tokens.** The prompt is about 7,100 tokens of 32,000. Every token removed is more room to work.

## Then: the moments

Each of these should make someone stop and show a friend. In rough order of value for effort.

Shipped: **`?fix`: the error you were about to spend an hour on.** See the README.

Shipped: **`?undo`: never afraid again.** See the README.

**`?recall`: your whole past, searchable.** "What was that command I used to fix nginx in March?" "Why did we pick Redis?" Across shell history, past sessions, notes, mail and documents, with the source cited, and none of it leaving the machine. The longer you use it, the more it's worth.

Shipped: **`?tonight`: a night shift.** See the README.

Shipped: **`?tour`: any codebase in five minutes.** See the README.

**`?setup`: a new machine feels like yours by lunchtime.** Your tools, config, keys workflow and habits, from what it knows about you. Tell it what's different and it adapts.

Shipped: **`?teach`: do it once, never again.** See the README.

Shipped: **`?receipts`: what exactly did it do, and how do we know?** See the README.

Shipped: **The guardian.** See the README.

Shipped: **`?learn`: a mentor, not an answer machine.** See the README.

**Offline packs.** Before a flight or an outage, it fetches the docs for your exact stack and versions. Then it works with no internet at all, including in places where connectivity can't be assumed.

**Decisions that explain themselves.** It notices decisions as you make them and records why. A year later, "why is it built this way?" has an answer.

**Your inbox, privately.** It triages, summarises and drafts in your voice, with mail nobody would paste into a cloud service. It never sends without you.

**Meetings and voice.** Local transcription into notes, decisions and reminders. Speak to it when your hands are full.

**For everyone who isn't a developer.** Forms, letters, tax paperwork and small-business records, in the language you think in, starting with English and नेपाली, with the documents staying at home.

## Next abilities (2026-11-08 brainstorm, in build order)

Not more harnesses: things it can't do yet.
1. **Hardware economy in `sakura-model`:** keep the system prompt's KV cache warm between turns; unload the driver after 20 idle minutes and reload on the next `?`; refuse a long eval or night job when the GPU is hot or has thrown an Xid this boot.
2. **Eyes:** `look FILE` with a local vision model that fits 8 GB: screenshots, error dialogs, scans, receipts, whiteboards.
3. **`?pr` and `?review`:** a PR from the branch with a body from the diff and commits; findings on a PR's diff. All through `gh`.
4. **Voice:** whisper.cpp in, Piper out; meetings into notes, decisions and reminders.
5. **The ntfy reply loop:** answer a push with "do it" and `pa` runs it; approve the night shift from bed.
6. **Long-running processes:** start a server, tail it, wake Sakura on a pattern.
7. **Structured data:** DuckDB on CSVs and logs as a one-line tool.
8. **The fleet:** what each machine is for, which has the GPU or RAM free, run it there; morning check that they're up.
9. **Clipboard in and out** (`wl-paste`, `wl-copy`): "fix the stack trace on my clipboard".
10. **`?red`:** a failing test, or one written from a sentence, iterated to green with a small diff.
11. **Schema snapshot per repo:** "which tables reference customer_id" without grepping migrations.
12. **`?try`:** a throwaway directory in the repo's language, runs a snippet, keeps nothing.
13. **Offline docs packs into `rag`:** Laravel 13, PHP 8.5, Vue 3, answers citing the right version with no network.
14. **Worktree workers:** each worker in its own `git worktree`, so two lanes are safe.
15. **Morning page:** brief, guardian, last night's report and the calendar on one screen at the day's first `?`.
16. **Mail that acts:** triage rules learned from you; calendar invites accepted or declined.
17. **Lazy skills and per-topic tool reference, a 2b router for classification, so the 9b and the driver wake only for real work.**
18. **Receipts and forms:** OCR into a ledger; tax paperwork in नेपाली and English from templates.

## Not doing

- Bypassing CAPTCHAs or bot detection, or anything that hides automation from a site.
- A hosted version, an account, or telemetry.
- Claiming a feature before an eval proves it.
- Stripping out the engine's safety section.
