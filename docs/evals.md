# Measuring it

One eval per feature, graded by planted input and real state, never by the model's say-so. Where things stand, and what is built but not yet proven enough, is in the [roadmap](../ROADMAP.md#where-it-stands).

```bash
python3 evals/run.py              # 31 cases, graded against live sources
python3 evals/ssh_chain.py        # ssh, pull and deploy on a throwaway container, graded inside it (needs docker)
python3 evals/coordinator.py      # workers and a coordinator session, graded by the repo's real state
python3 evals/wall.py             # the sandbox around workers, graded by a canary server and the disk
python3 evals/fix.py              # ?fix, graded by the command working afterwards and a canary for the one it mustn't rerun
python3 evals/undo.py             # ?undo, graded by file hashes
python3 evals/tour.py             # ?tour, graded by its citations existing and the real test command
python3 evals/tonight.py          # the night shift, graded by disk, git, a canary and the report
python3 evals/teach.py            # ?teach, graded by sakura-tool's gate and running the tool
python3 evals/abilities.py        # 60 checks: look, ledger, schema, procwatch, dq, offers, cron, drive, docpack, fleet, tbl, logs, worktrees
python3 evals/gpu.py              # sakura-gpu, 40 deterministic checks
python3 evals/torrent.py          # torrent, 19 deterministic checks
python3 evals/injection.py        # the trust boundary: injection detection + egress approval on every way out (http, scp, ssh, nc, DNS, git push, mail, the MCP path), the quarantine reader, the gateway's guard, 55 checks against a local site and planted transcripts
python3 evals/daily.py            # clip, ?decide/?why, ?morning, pa mail rules, fmt, ?watch, ?pr, ?review, ?try, hear, say: 156 checks, no model (--only NAME)
python3 evals/paper.py            # paper: templates in English and Nepali, VAT and totals, number words, the register, Devanagari in the PDF, BS dates: 86 checks
python3 evals/pa_devices.py       # fire-once across machines, stale claims, RRULE dates, repeat grammar, lingering, catch-up: 96 checks
python3 evals/gateway.py          # sakura-gateway against a fake homeserver and a fake signal-cli: pairing, the closed grammar, replay, no listener: 81 checks
python3 evals/map.py              # sakura-map: ranking, exact lines, the budget to the character, .gitignore, the cache, 3,000 files, 16 language tables, the hook: 130 checks
python3 evals/formats.py          # conv: books (epub, mobi, azw3, fb2), denoise, stems, ocr, LibreOffice documents and sheets: 63 checks, graded from the files written
python3 evals/memoryflows.py      # reflection, consolidation, 90-day flags, ?teach retro, the mail voice, ?recall over mail and documents: 69 checks, model stubbed
python3 evals/shim.py             # sakura-shim against a fake model server replaying mangled tool calls, streamed and not: 51 checks
python3 evals/guardian.py         # the guardian: disk projection from planted samples, certificates, late and unrestored backups, the weekly nag: 29 checks
python3 evals/machineroom.py      # ports, space, drift, when, conv (incl. redact/fill/sign), vid, dupes, shelve, money, sakura-doctor, sakura-notes, sakura-what, vault (Bitwarden, KeePassXC, 1Password), sakura-complete, sakura-last, sakura-model pick, sakura-suggest, sakura-lean, sakura-skill, the engine download, rag's Nepali and Hindi words, ledger export, host-scoped memory: 199 checks
python3 evals/archive.py          # faces, restore, conv subs, translate: planted faces and a spoken sentence; SKIP where the model isn't on this machine
python3 evals/toolpick.py         # does the model reach for the toolkit from a plain sentence? 15 asks graded by which commands ran (needs the driver) against planted state and a local server
evals/in-box.sh fix.py            # any of them inside a throwaway container; the driver stays on the host
```
