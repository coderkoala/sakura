# Roadmap

**The goal:** the thing people use once and say "I wish I had that 10 years ago." A senior colleague who lives in your terminal, knows your machines and your history, does the work and proves it, and never sends a word of it to anyone else.

## What must always be true

- **Yours.** Runs on your hardware. No account, no telemetry, no third party handling your work. Anything that leaves the machine is a request you asked for, to the source you asked.
- **Proven, not claimed.** It's done when a check says so, not when the model says so. Every feature has an eval graded by something other than the model.
- **Human work stays human.** CAPTCHAs, passwords and sends you asked to see first come to you. A site's refusal is final: no stealth, no solving, no disguise.
- **Mechanics over prompts.** When the model gets something wrong repeatedly, change what's possible, not what it's asked to do.

## Where it stands

Measured on one machine with an 8 GB GPU, driver Ornith 1.5 35B-A3B since 0.9.5 (run 30/30, wall 27/28; Qwen3.6 before it: 30/31, 27/28). Results vary between runs, so treat them as rates, not guarantees.

| Works, with an eval                                                                                                                                                                                                                                                                                                                         | Built, not proven enough                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multi-step work over ssh, with honest failure                                                                                                                                                                                                                                                                                               | Email with a real provider (tested on a local server only)                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Live facts from primary sources                                                                                                                                                                                                                                                                                                             | CAPTCHA hand-off on a real site (tested on a local page)                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Disposable workers and a coordinator                                                                                                                                                                                                                                                                                                        | Guards on the main agent (pattern matching, not a sandbox)                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Long tasks that used to crash a 32k context                                                                                                                                                                                                                                                                                                 | Tools it grows itself (a weak check can pass a weak tool)                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Local document search, office files, the shared browser                                                                                                                                                                                                                                                                                     | Anything on a second machine, or on real 6 GB hardware                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Reminders, briefs, watches, auto-reply                                                                                                                                                                                                                                                                                                      | Workers with `network: yes` (keys, agents and sockets hidden unless the job names them)                                                                                                                                                                                                                                                                                                                                                                                      |
| A sandbox around workers: no network, writes only where the job allows                                                                                                                                                                                                                                                                      |                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `?fix`, `?undo`, `?recap`                                                                                                                                                                                                                                                                                                                   | `?tonight` on a real night's queue (the eval runs one)                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `?tour` (9/9), `?tonight` (11/11)                                                                                                                                                                                                                                                                                                           | `?teach` (2/3 at best, 1/3 often: with the guard now sending the turn back until something is kept, the 3B-active model still loses its way in `sakura-tool keep`'s check about half the time) and `?learn` (no eval: nothing but a reader can grade a lesson)                                                                                                                                                                                                               |
| The guardian's checks and its disk projection (`evals/guardian.py`, 29 checks: planted disks, a fortnight of samples at a known rate, certificates with known end dates, a set clock)                                                                                                                                                      | The guardian's projection against a real disk's fortnight                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `sakura-gpu` (40 checks), `torrent` (19 checks and a live daemon lifecycle), `dl` (12 checks, byte-range resume proven), `sakura-backup` (27 checks, a real restore each run)                                                                                                                                                               | `fmt`, `?watch`, `drive` against a real Google/Microsoft account (local remote only so far)                                                                                                                                                                                                                                                                                                                                                                                  |
| `look` (OCR and the vision model), `ledger`, `schema`, `procwatch`, `dq`, `pa offer`, `pa cron`, `docpack`, `fleet`, `drive`, `tbl`, `logs`, workers in worktrees (`evals/abilities.py`, 60 checks)                                                                                                                                         | `hear`, `say`, `clip`, `?pr`, `?review`, `?red`, `?try`, `?morning`, `pa mail` rules, `?decide`/`?why` (smoke-tested by hand)                                                                                                                                                                                                                                                                                                                                                |
| A trust boundary: fetched content scanned for injection and bannered as data, smuggling characters stripped, data-egress to un-named hosts gated for approval, the answer checked for exfil sinks (`evals/injection.py`, 25 checks)                                                                                                         | Dual-LLM / quarantine split — one model still holds untrusted content and the tools; the egress gate is the compensating control                                                                                                                                                                                                                                                                                                                                             |
| The machine room: `ports`, `space`, `drift`, `when`, `sakura-notes`, `host:` memory, `sakura-doctor`; `conv` (incl. redact, fill, sign), `vid`, `dupes`, `shelve`, `money`, `sakura-what`, `vault`, `sakura-complete`, `sakura-last`, `sakura-model pick` (`evals/machineroom.py`, 133 checks; `vid` and `conv URL` against a local server) | `restore`, `conv subs`, `translate` (built; `evals/archive.py` proves each only where its model is present — the eval machine had no GPU, no Vulkan and no reach to Hugging Face; `faces` passed 5/5 there on the CPU); whether the model picks the toolkit from a plain sentence (`evals/toolpick.py`, 15 asks, needs the driver); `vid` against a real site with a browser login; `conv ocr` (ocrmypdf wasn't on the eval machine); LibreOffice conversions beyond txt→pdf |

## Next: make what exists trustworthy

1. **Run evals in a disposable machine.** `evals/in-box.sh EVAL` (2026-11-08) runs one inside a throwaway Ubuntu container that shares the host's network, so the driver stays on the host and nothing the eval installs lands here. Proven with `fix.py --only import-typo` (2/2 inside the box). Full runs still happen on the host until the container has had a complete pass.
2. **Real-world passes.** Scripted as checklists in `docs/real-world.md` (mail against a real provider, a real CAPTCHA with a human, a second device end to end), with a results table. Each needs an account, a screen or a machine, so a person runs them; OAuth-only mail providers are the open item.
3. **`pa` across devices.** Reminders that follow you, firing once, not on all seven. Repeating calendar events. Reminders that work while logged out.
4. **Runs in more places.** A build for older glibc and for ARM, and a real run on a 6 GB card.
5. **Fewer tokens.** Measured 2026-11-08 with the driver's tokenizer: `prompts/base.md` 1,874, `AGENTS.md` 2,824 (it grew with tonight's tools), `coordinator.md` 642, plus the engine's own text and the skills list. Every token removed is more room to work; AGENTS.md's tool reference is the place to cut, by topic, behind an intent-driven injection (abilities item 17). Built 2026-11-11 as `sakura-lean` (off by default): the short reference is 63% smaller (6,300 characters against 16,800), the web, trust-boundary, install and memory sections stay whole, every other topic is one line naming its commands, and `hooks/tool_reference.py` puts a topic's section beside the message that's about it, matched from the manuals with no model, at most two a message, once a session (12 checks: 23 plain asks each bring their section, small talk brings nothing). It changes what the model reads, so it stays off until `evals/run.py` and `evals/toolpick.py` pass with it on the driver.

## Then: the moments

Each of these should make someone stop and show a friend. In rough order of value for effort.

Shipped: **`?fix`: the error you were about to spend an hour on.** See the README.

Shipped: **`?undo`: never afraid again.** See the README.

Partly shipped: **`?recall`: your whole past, searchable.** Sessions, shell history, decisions and memory today; mail and documents still go through `himalaya` and `rag`. "What was that command I used to fix nginx in March?" "Why did we pick Redis?" Across shell history, past sessions, notes, mail and documents, with the source cited, and none of it leaving the machine. The longer you use it, the more it's worth.

Shipped: **`?tonight`: a night shift.** See the README.

Shipped: **`?tour`: any codebase in five minutes.** See the README.

Shipped (brief-based, no eval without a second machine): **`?setup`: a new machine feels like yours by lunchtime.** Your tools, config, keys workflow and habits, from what it knows about you. Tell it what's different and it adapts.

Shipped: **`?teach`: do it once, never again.** See the README.

Shipped: **`?receipts`: what exactly did it do, and how do we know?** See the README.

Shipped: **The guardian.** See the README. Its backup promise is real now: `sakura-backup prove` restores a real file from the latest snapshot, byte-compares it, checks the repo, and resets the nag (eval 27/27).

Shipped: **`?learn`: a mentor, not an answer machine.** See the README.

Shipped as `docpack`: **Offline packs.** Before a flight or an outage, it fetches the docs for your exact stack and versions. Then it works with no internet at all, including in places where connectivity can't be assumed.

Shipped: **Decisions that explain themselves.** `?decide` and `?why`; the model is told to record a decision when it hears one. See the README.

Partly shipped (`pa mail urgent|mute`, `pa autoreply`, drafts through himalaya; learning your voice not yet): **Your inbox, privately.** It triages, summarises and drafts in your voice, with mail nobody would paste into a cloud service. It never sends without you.

Shipped as `hear`, `hear --notes`, `say` and `?hear`: **Meetings and voice.** Local transcription into notes, decisions and reminders. Speak to it when your hands are full.

Partly shipped (`ledger` for receipts and records; forms and letters not yet): **For everyone who isn't a developer.** Forms, letters, tax paperwork and small-business records, in the language you think in, starting with English and नेपाली, with the documents staying at home.

## Abilities (2026-11-08 brainstorm). Built the same day unless marked.

Not more harnesses: things it couldn't do before. Built means it runs and was smoke-tested by hand; only `?tour`, `?tonight` and the worker wall have evals. The rest need evals before the table above can claim them.

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
17. **Per-topic tool reference: built as `sakura-lean`, off by default** (see "Fewer tokens" above; matched from the manuals, so no 2b router was needed for it). Not built: a 2b router so the 9b and the driver wake only for real work. Turning lean on by default waits for a full eval pass on the driver.
18. **Receipts and forms:** OCR into a ledger; tax paperwork in नेपाली and English from templates.

## Memory workflows, next (2026-11-09 brainstorm)

Built: recall on back-references (`hooks/recall_context.py`), project notes (`.sakura.md`). The rest, in build order:

1. **Reflection passes:** a nightly `pa job` reads `?recap` and proposes `sakura-memory add` lines as offers; yes writes them. The model never writes memory silently.
2. **`?teach retro`:** mine the last session, not shell history, for a repeatable procedure, through the same `sakura-tool keep` gate.
3. **A voice profile for mail:** learned locally from sent mail into a style note that drafting reads. The roadmap's "inbox in your voice".
4. **Consolidation:** when a full store refuses a write, a model pass proposes merges as offers; facts unretrieved for 90 days get flagged.
5. **Fleet-scoped memory:** a `host:` prefix so facts about one machine don't load on another; the stores already sync through dotfiles.
   Skipped deliberately: temporal knowledge graphs (heavy infra; FTS over sessions and decisions already answers why/when at this scale).

## Trust boundary (2026-11-09 — V1 goal shipped)

The goal: **protect outgoing networks where a model does as a page tells it — every action from a
remote source needs explicit approval, and injection is detected on the machine.** Indirect prompt
injection has no prompt-level cure (a guardrail is just more text the next injection argues with), so
this is built as two deterministic mechanics, each with an eval graded by real behaviour, not the
model's say-so. Full write-up and threat model: [docs/trust-boundary.md](docs/trust-boundary.md).

1. **Content in is data.** `mcp/sakura-web/injection.py` scans everything fetched — `fetch_url` (so
   `live research` and the grounding hook too), `web_search`/`curated_search`/`wikipedia`, the browser's
   `open`/`read`, and `rag search` passages. It strips invisible/bidi/Unicode-tag smuggling characters
   (decoding the tag block first, so an order hidden in "blank" text is caught), and fences any content
   that tries to give the model orders or beacon data out with a _this is data_ banner. Measured at 0
   false positives on the repo's own prose and on ordinary API docs. `sakura-scan` runs it on demand.
2. **Data out stops for approval.** `hooks/egress_guard.py` gates every shell command and the final
   answer: a request that _sends data_ (a body, a substitution, a `?data=` beacon) to a host the user
   never named asks for approval via the `q`/`w` overlay even when `sakura-trust` is on; reading is never
   gated; the allowlist (`rules/egress-allow.txt`) and any host the user named are trusted, so a host
   that first appeared in a fetched page isn't. The answer is blocked if it hides an exfiltration sink.

Also fixed here: the Stop-hook "do it now, not a plan" nag no longer fires when the user asked for a
plan/design/advice, or in a coordinator session (which plans and delegates by design) — it was firing
on legitimate plan turns (`hooks/claim_check.py`, covered in its selftest and `evals/injection.py`).

Next, if the appetite is there: a real quarantine split (a content-only model with no tools feeding a
privileged model that never sees raw untrusted text); egress accounting across non-shell tool paths.

## The machine room, and the no-upload rule (2026-11-09 brainstorm)

Two threads. First, the questions a senior colleague answers in one line that still took a chain of `ss`, `du`, `diff` and
crontab-reading: all built the same day, model-free, 85 checks.

1. **`ports`:** what's listening, who holds it (pid, user, unit, container), from `/proc` so it works everywhere; over ssh too.
2. **`space`:** what's eating the disk by category with a verdict, and a `clean --go` that only ever touches what rebuilds itself. The guardian's disk finding now points here.
3. **`drift`:** a file, the packages, the enabled units or the authorized keys across the fleet, only the differences.
4. **`when`:** cron and OnCalendar in English with the next firings; `--timers`.
5. **`host:` memory** (memory workflows item 5): a fact about one machine loads only there.
6. **`sakura-notes`:** release notes from the commits since the last tag, so `sakura-release` has honest input.

Second, the rule: **nothing of yours is uploaded to be converted.** The web is full of sites that take a PDF, a photo or a video
to merge, compress, OCR, strip or convert it, and keep a copy. Every one of them runs ffmpeg, pandoc, qpdf, ghostscript,
ImageMagick, LibreOffice or tesseract underneath. So: 7. **`conv`:** those tools behind one command that picks the right one, never overwrites an input, asks for a PDF password on the terminal and passes it over a pipe, and strips EXIF/GPS/author before a file is shared. The agent is told never to suggest a website for any of it. 8. **`vid`:** yt-dlp the way an archivist uses it — metadata, thumbnail, subtitles and the info.json kept, a download archive so a channel or playlist resumes and fetches only what's new, a browser's own login for private videos and never a password. For keeping your own past videos, and the people in them.

Next along the same line, not built: **`conv subs VIDEO`** (subtitles from `hear`, burned in or as .srt, in the language spoken);
**faces and places in your photo library**, locally (who's in this picture, every photo of her), with the embeddings never leaving;
**upscaling and restoring** old video and scans with a local model; **ebooks** (epub↔mobi↔pdf for a reader); a **print-to-PDF path
for web pages** through the shared browser. Each needs a deterministic eval before it can be claimed. Built the same evening, with
checks: **`vid watch URL`** (what's new on a channel since the last look; exit 1 when there is, so `pa job every sunday 9am: vid watch …`
nags), **`conv extract`** (zip, tar, 7z, rar into their own folder; entries pointing outside it, and links, refused), **`conv URL --to pdf|png|md`** (the local headless browser prints the page), **`dupes`** (the same file by content across drives, kept once by hard link or deleted, dry run first), **`shelve`** (photos and videos into `YEAR/YEAR-MM` by the day taken, sidecars along), and **`sakura-doctor`** (is the install whole; it found twenty commands that didn't answer `--help`, now fixed, so the README's promise is checked, not assumed).

## Ease of access (2026-11-09, from the user: "I may not remember everything; it has to be dependable")

Eighty-odd commands are only a feature if nobody has to remember them. Built the same evening, each with checks:

1. **`sakura-what`** (`?what`): the command for any ask, from the manuals, no model; alone, everything by situation; `?how` consults it first.
2. **`vault`** (`?otp`): passwords and 2FA from `pass`, clipboard not screen, Bitwarden import with TOTP seeds; the agent never asks for or prints a secret.
3. **The doctor on the morning page** and at the end of `install.sh`.
4. **`?docs`** over the docs packs and your documents.
   Then, the same night, with checks: **Tab completion for every command** (`sakura-complete`, generated from the manuals, so it can't drift), **`vault import keepassxc|1password`**, and **`?last`** (what was I doing: the last turn's directory, ask and answer, from the record; it cd's there). Then (2026-11-11), with 18 checks: **a `?` with nothing typed offers the three most likely things** (`sakura-suggest`, no model): the command that just failed in this shell, a merge stopped on conflicts, an offer waiting for a yes, last night's report, the guardian's findings, uncommitted work, commits without a PR, a due to-do, what you last asked here, the tour of a repository it has never seen, the morning page, the day's recap. 1-3 does one, Enter opens Sakura as before; `sakura-suggest off` turns it off.

## Your models (2026-11-09, from the user: "let the user select what models they want, via whatmodel.sh as well")

Built, with checks (13 in `evals/machineroom.py`): `sakura-model pick` for every job and the driver; a menu of what's been tried with Sakura, what Ollama has, and whatmodel.sh's ranking for this machine (asked first; RAM and VRAM only), with a Hugging Face GGUF lookup for entries that carry no tag; your own GGUF as the driver, pinned on first download; one choices file every tool reads, environment variables still winning for a run; a per-user catalog so a picked model keeps Sakura's prompt. Found on the way: the fast tier had been running without Sakura's prompt, since its slug wasn't in the catalog; fixed by the same catalog. Not proven: a picked model's quality — `evals/run.py --model TAG` on your machine is what says whether it can drive.

## Everything (2026-11-09 research)

Three research passes — open-source tools by everyday use, open-weight models by want on 8 GB, and what the other local
agents of 2026 offer — are mapped in [docs/everything.md](docs/everything.md): for each want, the tool the web services run
underneath, the model that fits, what Sakura does today, and what's next. The build order it ends with, each needing an eval
first (done the same day, with checks: `conv redact|fields|fill|sign|verify` and `money` on hledger): `conv subs|denoise|stems` →
`restore` (Real-ESRGAN, RIFE, SeedVR2) → `faces` (InsightFace + SigLIP 2, local only) → the Nepal paperwork templates on `conv fill` →
`translate` (Argos/NLLB) and Nepali/Hindi embeddings for `rag` → kept procedures, a repo map and a tool-call shim → a messaging gateway with pairing, last and default-closed.

## Not doing

- Bypassing CAPTCHAs or bot detection, or anything that hides automation from a site.
- A hosted version, an account, or telemetry.
- Claiming a feature before an eval proves it.
- Stripping out the engine's safety section.
