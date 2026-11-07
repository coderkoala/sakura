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

## Next: make what exists trustworthy

1. **Run evals in a disposable machine.** They run on the real host with sudo today, and have left containers and packages behind.
2. **Real-world passes.** A real mail provider, including OAuth for those that require it. A real CAPTCHA in the visible window. A second device end to end.
3. **`pa` across devices.** Reminders that follow you, firing once, not on all seven. Repeating calendar events. Reminders that work while logged out.
4. **Runs in more places.** A build for older glibc and for ARM, and a real run on a 6 GB card.
5. **Fewer tokens.** The prompt is about 7,100 tokens of 32,000. Every token removed is more room to work.

## Then: the moments

Each of these should make someone stop and show a friend. In rough order of value for effort.

**`?fix`: the error you were about to spend an hour on.** A command fails. Type `?fix`. It already has the command, the output and the directory, and it fixes the cause, or tells you what it found. No copying, no pasting, no explaining.

**`?undo`: never afraid again.** Every change it makes is snapshotted first. One key puts everything back, however many files it touched. This changes what people dare to ask for.

**`?recall`: your whole past, searchable.** "What was that command I used to fix nginx in March?" "Why did we pick Redis?" Across shell history, past sessions, notes, mail and documents, with the source cited, and none of it leaving the machine. The longer you use it, the more it's worth.

**`?tonight`: a night shift.** Queue work before bed. It runs while the GPU is idle, each job verified, and in the morning you get a report and diffs to approve. Nothing is pushed or sent without you.

**`?tour`: any codebase in five minutes.** Clone something unfamiliar or inherit a legacy system. It reads it and walks you through what matters, where the bodies are buried, and how to run it, citing files and lines.

**`?setup`: a new machine feels like yours by lunchtime.** Your tools, config, keys workflow and habits, from what it knows about you. Tell it what's different and it adapts.

**`?teach`: do it once, never again.** Show it a task, or point at what you just did in the shell. It writes a tested tool or a recurring job, proven by the same gate `sakura-tool` uses.

**`?receipts`: what exactly did it do, and how do we know?** A plain record of every action, why it was taken and what proved it. Trust you can audit, and an answer to "what changed on this box last week?"

**The guardian.** It quietly watches what's easy to forget, and tells you before it hurts: the disk that fills in nine days, the certificate ending soon, and above all the backup that has never been test-restored. It proves backups by restoring them.

**`?learn`: a mentor, not an answer machine.** It explains why as well as what, at your level, and remembers what you already know. For the junior who has nobody to ask at 2am.

**Offline packs.** Before a flight or an outage, it fetches the docs for your exact stack and versions. Then it works with no internet at all, including in places where connectivity can't be assumed.

**Decisions that explain themselves.** It notices decisions as you make them and records why. A year later, "why is it built this way?" has an answer.

**Your inbox, privately.** It triages, summarises and drafts in your voice, with mail nobody would paste into a cloud service. It never sends without you.

**Meetings and voice.** Local transcription into notes, decisions and reminders. Speak to it when your hands are full.

**For everyone who isn't a developer.** Forms, letters, tax paperwork and small-business records, in the language you think in, starting with English and नेपाली, with the documents staying at home.

## Not doing

- Bypassing CAPTCHAs or bot detection, or anything that hides automation from a site.
- A hosted version, an account, or telemetry.
- Claiming a feature before an eval proves it.
- Stripping out the engine's safety section.
