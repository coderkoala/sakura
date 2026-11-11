# Everything: a map of wants to local tools, local models, and Sakura

Researched 2026-11-09 (three passes: open-source tools by everyday use, open-weight models by want, what other local agents
offer). Release dates and VRAM figures were checked against project pages that day; where a claim couldn't be read at the
source it says so. The rule this map serves: **nothing of yours goes to a web service when a widely used open-source tool
does the same job on your machine**, and **a model is "available" only if it runs on 8 GB of VRAM and 32 GB of RAM**.

Columns: what you want · the tool everyone runs underneath the SaaS · the local model if one is needed · what Sakura
already does · what Sakura should do next. "Built" means it runs and has an eval; "next" is ordered by value for effort.

## 1. Documents (the ilovepdf problem)

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| merge, split, rotate, pick pages, unlock, compress | qpdf 12.4 (2026-09), ghostscript, poppler | — | `conv merge\|split\|pages\|rotate\|unlock\|compress` (eval) | — |
| OCR a scan, incl. Devanagari | OCRmyPDF 17.14 (2026-11) + Tesseract 5.5 (`tesseract-ocr-nep`, `-hin`); Surya OCR 0.23 for layout-heavy Indic pages | GLM-OCR 0.9B (~2.7 GB, Ollama), PaddleOCR-VL 1.5, dots.ocr; Qwen3-VL-8B best open model on a 2026 Devanagari stress test (chrF++ 75) but printed scans still collapse 9/10 systems | `conv ocr` (ocrmypdf, else tesseract); `look --text` (tesseract) | `conv ocr --langs nep+hin+eng` default from the machine's installed packs; a `look --read` path through GLM-OCR for handwriting and bad scans; eval against planted Devanagari renders |
| office ↔ pdf, md ↔ docx/epub/html | LibreOffice 26.8 headless, pandoc 3.13 | — | `conv FILE --to …` (eval for txt→pdf, md→html/docx) | eval for docx→pdf and epub; `--to mobi/azw3` via calibre's `ebook-convert` when present |
| redaction, form filling | PyMuPDF 2.1 (`add_redact_annot`), pdfcpu 0.16 (`form fill in.pdf data.json`) | — | — | `conv redact FILE "pattern"` (PyMuPDF, real removal not a black box) and `conv fill form.pdf data.json`; the roadmap's "forms and letters in नेपाली" sits on this |
| e-signing | pyHanko 0.38 (PAdES, timestamps); DocuSeal 3.3 for multi-party | — | — | `conv sign FILE --key …` through pyHanko; the key stays in `pass`/`age` |
| scanning from a phone | OpenScan (Android) → Paperless-ngx 3.4 consume folder | — | `ledger add` reads receipts | a `paperless` wrapper is low value: Paperless already has a CLI/API; `rag index` the consume folder instead |
| web page to pdf | Chromium headless, SingleFile/monolith for a faithful .html | — | `conv URL --to pdf\|png\|md` (eval) | `conv URL --to html` through `monolith` when present (one self-contained file, no browser) |
| strip metadata before sharing | ExifTool 13.61, mat2 0.15 | — | `conv strip` (exiftool, else magick/ffmpeg/pypdf) (eval) | — |

## 2. Photos and the family archive

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| order by the day taken | ExifTool (`'-Directory<DateTimeOriginal'`) | — | `shelve DIR --into LIB` (EXIF, video creation time, name, mtime marked) (eval) | `shelve --fix-dates` to write a date into files that only have one in their name |
| duplicates across drives and backups | czkawka_cli 12 (also *similar* images), fclones | — | `dupes` (exact, by content; link or remove) (eval) | `dupes --similar` through czkawka's perceptual hash when installed, for the same photo at two sizes |
| who is in this picture; every photo of her | InsightFace buffalo_l (326 MB, non-commercial licence), DBSCAN clustering; Immich uses it | SigLIP 2 / JinaCLIP-v2 for "a photo of grandma cooking" search, 109-language text tower | — | **`faces`**: index a library on the GPU, cluster, let the user name a cluster once, then `faces find "grandma"`; embeddings never leave `~/.sakura`. Eval: planted renders of two synthetic faces |
| RAW, HEIC, panorama, HDR | darktable-cli 5.6, RawTherapee 5.13, libheif, Hugin 2026 + enfuse | — | `conv x.heic --to jpg` | `conv --to jpg` for RAW through darktable-cli when present; `conv panorama *.jpg` through Hugin |
| strip GPS and camera data | ExifTool | — | `conv strip` | — |
| restore old scans | Real-ESRGAN ncnn-vulkan (no CUDA needed), `realesr-general-x4v3 -dn` | Real-ESRGAN; SeedVR2 3B GGUF for video (8 GB is an experimental target) | — | **`restore`**: `restore photo.jpg` (Real-ESRGAN, portable binary), `restore --video clip.mp4` (Real-ESRGAN per frame + RIFE 4.26 interpolation, SeedVR2 when it fits), `restore --color` (DDColor); eval by PSNR against a downscaled original |

## 3. Video and sound

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| keep your own videos | yt-dlp 2026.10, gallery-dl 1.32 for image hosts | — | `vid`, `vid archive`, `vid watch` (eval) | `vid` over gallery-dl for photo albums on the same sites |
| transcode, trim, gif, shrink, contact sheet | FFmpeg 8.1, HandBrakeCLI 1.11 for presets, gifski for quality gifs | — | `conv` trim/audio/gif/thumbs/shrink (eval) | — |
| subtitles and transcripts, incl. Nepali/Hindi | whisper.cpp 1.9 (large-v3-turbo; 99 languages incl. Nepali), WhisperX for word timing + speakers | Whisper large-v3-turbo (~1.6 GB); Qwen3-ASR 1.7B (Jan 2026, Apache-2.0, 52 languages incl. Hindi, Nepali unverified); Meta Omnilingual ASR (1,600+ languages, no GGUF runtime yet) | `hear FILE` (faster-whisper on CPU), `hear --notes` | **`conv subs VIDEO [--lang ne] [--burn]`**: `.srt` from `hear`, burned in with ffmpeg on request; speaker labels through pyannote `community-1` when installed. Eval: a synthetic voice clip with known words |
| a relative's voice, kept (with consent) | — | Qwen3-TTS 1.7B (3-second cloning, 10 languages, no Nepali/Hindi); Chatterbox (English, watermarked); Kokoro-82M (4 Hindi voices, no cloning); Piper "Nepali Voices v0" (the only Nepali TTS found) | `say` (Piper, else spd-say) | `say --voice-from sample.wav` through Qwen3-TTS, gated on the user saying whose voice and that they may; never from a fetched clip |
| podcasts, audiobooks, loudness | ffmpeg-normalize 1.44 (EBU R128), m4b-tool | — | — | `conv normalize` and `conv audiobook chapters/` |
| clean up sound; separate voices from music | DeepFilterNet3 (CPU, realtime), Resemble-Enhance, Demucs htdemucs / BS-RoFormer | DeepFilterNet3 (2M params); BS-RoFormer (SOTA separation) | — | `conv denoise` (DeepFilterNet) and `conv stems song.mp3` (Demucs) — old family tapes are the use |
| screen recording | wf-recorder 0.6 (Wayland), OBS 33, vhs for terminals | — | — | `rec` (start/stop detached, like `procwatch`) — low priority |

## 4. Knowledge, notes, search

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| find anything I've ever saved | ripgrep-all 0.10 (PDF, docx, sqlite, zip), Recoll 1.43 | Qwen3-Embedding 0.6B (~1 GB) or BGE-M3 for Hindi/Indic; a fine-tuned multilingual-E5 beat BM25 on Nepali QA (2026) | `rag` (local embeddings), `sakura-recall` (FTS over sessions, shell, decisions, memory) | `rag` switches to Qwen3-Embedding 0.6B for Nepali/Hindi documents; `sakura-recall` summarises long hits instead of dumping them |
| notes, journal, flashcards | zk 0.15, Joplin CLI, jrnl 4.6, Anki 26.09 + apkg | — | memory, decisions, `.sakura.md` | `?learn` writes an Anki deck (`apkg`) from what it just taught; "make me cards from this PDF" |
| offline docs for my stack | Sakura's `docpack` | — | `docpack add laravel@13` | — |
| bookmarks, read-later, feeds | buku, linkding, wallabag/Karakeep, Newsboat 2.45 / Miniflux 2.3 | — | `live news`, `fetch_url` renders feeds | `keep URL` (a SingleFile/monolith copy + `rag index`) — "save this for later" without Pocket |
| translation, Nepali ↔ English ↔ Hindi | Argos Translate 1.11 (has en↔ne, en↔hi), LibreTranslate 1.9 | NLLB-200 distilled 600M (explicit `npi_Deva`, CC-BY-NC); Gemma 4 E4B (140+ languages, Nepali untested) | the `translator` skill (model) | `translate FILE\|"text" --to ne` through Argos offline, the driver for nuance; eval with a fixed sentence pair |

## 5. Mail, calendar, people, messages

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| mail without webmail | himalaya 2.2, aerc, notmuch + mbsync | the driver, for drafts | `himalaya`, `pa mail urgent\|mute`, `pa autoreply` | the voice profile from sent mail (memory workflows item 3) |
| calendar and contacts off Google | vdirsyncer 0.21 + khal 0.14 + khard 0.22; Radicale 3.9 to self-host | — | `pa remind` | `pa` reads khal: "what's on today" in the brief; invites accepted/declined from mail (abilities item 16) |
| messages: Signal, WhatsApp, SMS | signal-cli 0.14; Matrix (Synapse/Tuwunel + mautrix bridges) to hold them in one place; KDE Connect for SMS through the phone | — | `pa offer` / `pa listen` over ntfy (the two-way phone) | **a gateway with pairing**: one local process for Signal/Matrix that delivers `pa` reminders and night reports and takes "do it" replies, loopback-only, pairing by code, the egress guard applied — the single most-wanted feature in every 2026 agent, and the one with the worst security record (OpenClaw: 21k–30k instances found open on the internet, CVE-2026-25253). Default closed |
| calls | Jitsi, Galène (one Go binary), Nextcloud Talk | — | — | not Sakura's job |

## 6. Money and paperwork

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| receipts into a ledger | Paperless-ngx, Sakura's `ledger` | the vision model (`look`) | `ledger add receipt.jpg` (eval) | `ledger export --hledger` so the ledger is plain-text accounting |
| bank statements, budgets | hledger 1.52 (CSV rules import), beancount 3 + fava, Actual Budget 26.11 (web) | — | `dq` over CSVs | `money import bank.csv` through hledger's rules, `money month` — plain text, no bank credentials anywhere |
| invoices, receipts, quotations | Invoice Ninja (self-host) | — | `paper new invoice --item "desc,qty,rate"`: VAT 13% in whole paisa, the total in words, numbered per fiscal year in a plain-text register (eval) | a VAT-inclusive mode for retail bills; `paper register --hledger` straight into `money` |
| letters and forms (Nepal, English + नेपाली) | pandoc + LibreOffice with a Devanagari font; pypdf form fill; no open-source Nepal tax tool exists | — (templates, no model) | `paper`: ten letter and bill templates in both languages, Bikram Sambat dates from a table (2000–2083), `paper fill FORM.pdf` for an office's own PDF form through `conv fill` (eval) | the BS table past 2083 as each year's calendar is published; the driver for free-text bodies; more templates |

## 7. The machine room and the fleet

| Want | Tool | Model | Sakura today | Next |
|---|---|---|---|---|
| what's listening, what's eating the disk, how do my machines differ, when does this run | (Sakura's own, over `/proc`, `du`, ssh, cron parsing) | — | `ports`, `space`, `drift`, `when` (eval) | `drift --fix FILE HOST` to push the baseline out, with a diff shown first |
| is the install whole | — | — | `sakura-doctor` (eval; found 20 broken `--help`s on day one) | run it inside `evals/in-box.sh` so a fresh container proves install.sh |
| backups that are proven, sync, cloud drives | restic 0.19, Syncthing 2.1, rclone 1.76 | — | `sakura-backup prove`, `drive` | `sakura-backup` over Borg for people who already have one |
| smart home, printers, scanners, the LAN | hass-cli 1.0, nmap 7.99 / arp-scan, SANE `scanimage`, CUPS | — | — | `home` (hass-cli wrapper with the egress guard: Home Assistant is on the LAN, named by the user) and `scan` (scanimage → `conv ocr`) |
| passwords and 2FA | pass + pass-otp, gopass 1.17, KeePassXC 2.8 CLI, oathtool | — | `pass` for himalaya; never read by the agent | `?otp github` prints a code through pass-otp — the agent never sees the secret, only the 6 digits it asked for |

## 8. The models (what fits 8 GB in late 2026)

| Want | Pick | Why | Runs as |
|---|---|---|---|
| the driver (tools, agentic) | Qwen3.6-35B-A3B (Ornith 1.5 abliterated) — current | MoE with 3B active: llama.cpp `--n-cpu-moe` keeps experts in RAM and 30+ tok/s on 8 GB; SWE-bench Verified 73.4 (vendor) | `sakura-model` today |
| alternatives | GLM-4.7-Flash 30B-A3B (MIT), Gemma 4 26B-A4B (Apache-2.0), gpt-oss-20b | same footprint class; Gemma 4 ranked just below Qwen3.6 on open leaderboards | `sakura-model driver NAME` once a driver file is added and `evals/run.py` passes |
| fully resident fast tier | Qwen3.5 9B dense Q4 (~5.5 GB) — current 9b; Spark-X2.6 4B | no RAM traffic | `SAKURA_FAST=1` |
| eyes | Qwen3-VL 8B/4B; GLM-OCR 0.9B for documents; Gemma 4 E4B for general vision | DocVQA 96; best open Devanagari | `look` (Qwen2.5-VL 3 GB today) → `sakura-model` gains a `vision` slot |
| ears | Whisper large-v3-turbo; Qwen3-ASR 1.7B; pyannote for who-spoke | 99 languages incl. Nepali / 52 incl. Hindi | `hear` |
| voice | Piper (Nepali Voices v0 for ne); Kokoro-82M (Hindi); Qwen3-TTS for cloning | CPU-fast; cloning needs 4–6 GB | `say` |
| pictures | Z-Image Turbo (GGUF Q4, ~6.9 GB peak), FLUX.2 klein 4B (Apache-2.0, editing), FLUX.1-dev GGUF for inpainting; BiRefNet for backgrounds | the three that fit 8 GB in 2026 | the `image` skill (stable-diffusion.cpp) → ComfyUI-GGUF path |
| restoration | Real-ESRGAN (ncnn, no CUDA), RIFE 4.26, DDColor, SeedVR2 3B GGUF (experimental on 8 GB) | the family-video use | `restore` (next) |
| embeddings | Qwen3-Embedding 0.6B (100+ languages), BGE-M3 | Nepali/Hindi RAG | `rag` |
| translation | NLLB-200 600M (`npi_Deva`), Argos | the only ones with explicit Nepali | `translate` (next) |
| separation, denoise, music | BS-RoFormer / Demucs, DeepFilterNet3, ACE-Step 1.5 (2B turbo fits 6–8 GB) | tapes and songs | `conv stems\|denoise` (next) |
| faces | InsightFace buffalo_l + SigLIP 2 | personal library only (licence) | `faces` (next) |

What changed in 2026, in one line each: MoE-with-expert-offload put 30–35B models on 8 GB cards; Qwen shipped an Apache-2.0
speech stack (ASR with Hindi, TTS with 3-second cloning, no Indic TTS); sub-1B document VLMs (GLM-OCR, PaddleOCR-VL) beat
7B models at reading pages; Z-Image and FLUX.2 klein made image editing fit 8 GB; SeedVR2 brought temporal video restoration
to the edge of 8 GB; Gemma 4 (Apache-2.0) is the non-Qwen alternative for vision and translation. Still missing: a verified
Nepali TTS beyond a community Piper model, any Nepali ASR benchmark, and commercial-use licences for InsightFace, NLLB and
RMBG-2.0.

## 9. What the other agents do that Sakura should borrow (and what to avoid)

From Hermes Agent, Goose, Aider, OpenHands, Claude Code, Khoj, Open WebUI, LocalAI, Home Assistant, OVOS, OpenClaw and the
2026 computer-use projects. Ranked for a single user, private, terminal-first:

1. **Procedures that are kept, not just scripts** (Hermes, Codex, Claude Code skills): after a hard task, write a SKILL.md in the agentskills.io shape, load it by name next time. `?teach` keeps tools; this keeps know-how. Import from other agents' skill folders — through `sakura-scan` first, since one audit found 36% of a marketplace's skills carrying injection.
2. **A repo map** (Aider): a tree-sitter symbol graph ranked by relevance, injected for code tasks; the biggest quality lever for a small model on a big codebase. `?tour` gathers the facts already; this makes them a standing context.
3. **A tool-call shim** (Goose): a tiny second model that repairs text-shaped tool calls from a model that mangled the JSON. On 8 GB with abliterated models this is the reliability gap `evals/run.py` measures.
4. **Recipes** (Goose): `sakura-worker` jobs with `{{params}}`, a JSON schema for the report, `on_failure` cleanup — so night-shift jobs are reusable files, not pasted briefs.
5. **Lint-test-fix and commit per step** (Aider): after an edit in a repo, run `fmt --lint` and the tests, fix, commit, so `git` is the fine-grained undo alongside `?undo`.
6. **`ask_user` as a first-class move, and a plan-only mode** (Open WebUI, Cline, Claude Code): the model pauses with a question instead of guessing; `??` is close to plan mode already.
7. **The gateway with pairing** (Hermes, OpenClaw, Claude Channels): see §5; loopback-only, pair by code, egress-guarded.
8. **A deterministic fast path for voice** (Home Assistant, OVOS): timers, reminders, "what time is it" answered by `pa` in under a second before any model wakes; the intent router already classifies.
9. **Roaming access without open ports** (Goose over iroh/QUIC): reach the running agent from a phone over a key-pinned tunnel. Pairs with 7; same default-closed rule.
10. **Session search that summarises** (Hermes): `sakura-recall` with a model summary of long hits and a `?insights` of what you ask most.
11. **Harness profiles per model** (Open Interpreter's `/harness`): prompting shaped to the driver (qwen-code shape today), measured by `evals/run.py` before switching.
12. **Per-conversation sandboxes and webhook triggers** (OpenHands): workers already sandbox; a `pa job` fired by a webhook (`watch_url`-style) would close the loop with CI and the fleet.

Avoid, with the evidence: agents reachable from the internet by default (OpenClaw, 2026); skill marketplaces installed
without scanning (ToxicSkills, ClawHavoc); MCP tools whose definitions change after approval (40+ MCP CVEs by April 2026 —
pin definition hashes, re-approve on change); agents holding production credentials (PocketOS, April 2026: a token found in
the repo, the database and its backups gone in nine seconds — Sakura's workers can't see keys unless the job names the kind,
and night jobs never can; keep it that way); LLM-judged approval as the only gate (Goose documents its read/write
classification as "best-effort" — Sakura's floor is rules: the guard, `safe-reads.rules`, the egress gate).

## 10. The build order from here

Each needs a deterministic eval before the roadmap table can claim it.

1. `conv subs` (whisper → .srt, burn-in) and `conv denoise|stems` — the family tapes, end to end: `vid archive` → `shelve` → `dupes` → `conv subs` → `restore`.
2. `restore` (Real-ESRGAN ncnn for photos; per-frame + RIFE for video; SeedVR2 when it fits).
3. `faces` (InsightFace + SigLIP 2; the library never leaves the machine).
4. `conv redact|fill|sign` (PyMuPDF, pdfcpu, pyHanko) — the rest of the ilovepdf list, and the Nepal paperwork templates on top.
5. `translate` (Argos offline, NLLB when quality matters) and `rag` on Qwen3-Embedding for Nepali/Hindi.
6. `money` (hledger rules import) and `ledger export --hledger`.
7. Skills kept as procedures (§9.1), the repo map (§9.2), the tool-call shim (§9.3) — the three that make the model itself better.
8. The gateway with pairing (§9.7), last, because it's the one that can hurt if it's wrong.

### Where the build order stands (2026-11-11)

1. Built: `conv subs`, `conv denoise`, `conv stems` (`evals/archive.py`, `evals/formats.py`; real stem separation and `--model` denoise unproven where the evals ran).
2. Built: `restore` (proven only where its models are present). SeedVR2 not attempted.
3. Built: `faces` (`evals/archive.py`, 5/5 on a CPU). SigLIP 2 for places not built.
4. Built: `conv redact|fields|fill|sign|verify`, and the paperwork on top as `paper` (`evals/paper.py`): ordinary letters and bills in English and Nepali, never an invented official form.
5. Built: `translate`; `rag` and `?recall` now keep Devanagari words whole (they were being cut at every vowel sign). Nepali recall of the embedding model is unmeasured.
6. Built: `money`; `paper register --hledger` hands issued invoices to it. `ledger export --hledger` built (receipts as entries hledger accepts).
7. Built: `sakura-skill` (§9.1) and `sakura-shim` (§9.3, deterministic repairs, no second model). The repo map (§9.2): see the roadmap.
8. Built: `sakura-gateway` (§9.7), default closed, proven against a fake homeserver and a fake signal-cli only.
