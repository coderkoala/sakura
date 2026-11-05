# Sakura — machine and tool reference

How to work is in Sakura's base instructions. This file is the reference for this machine's tools.

## Web knowledge (shell commands; they never need approval)
- `wikipedia "<topic>"` — Wikipedia summary + URL. The primary source; never CAPTCHA-blocked.
- `web_search "<query>" [n]` — Wikipedia-first, plus search-engine results when the engines answer.
- `fetch_url "<url>" [chars]` — readable text of any page, follows redirects, renders RSS/Atom feeds. On a thin
  blog or news index it prints the site's feed URL: fetch that to read every entry at once.
- `curated_search <persona> "<query>"` — your persona's authoritative sites (HackTricks, MDN, official docs, …).
- Before you answer, a hook injects lookups it already ran for you: Wikipedia and Wikidata for current office-holders, package
  registries for a tool's latest version, this project's own manifest versions. Use them; don't redo them.
- DuckDuckGo and SearXNG often serve this host a CAPTCHA. Never curl a search engine.

## Specialist models
`consult <role> "<question>"` gets a one-shot answer (no tools, no session) from a specialist local model:
`coder` (hard code, algorithms), `coder-fast` (quick snippets), `reason` (deeper analysis), `security`, `prose`.
Only the driver model (Qwen3.6 or qwen3.5, picked by `sakura-launch`) runs a session here; reach every other model through `consult`.

## Root, installs, GUI
- `sudo -A <command>` — askpass is configured, so it never blocks on a password prompt.
- Missing tool: `command -v` first, then `sudo -A apt-get install -y PKG`, `uv tool install PKG` (Python CLIs),
  `cargo install`, `go install`, an upstream release binary into ~/.local/bin, or a Docker image.
- GUI apps start detached: `setsid -f xclock >/dev/null 2>&1`.

## Remote machines
Hosts are in ~/.ssh/config. Connections are multiplexed, so many ssh calls are cheap.

## Memory
- Your saved facts arrive at the start of a session. They hold about 3000 characters, so keep only what will matter next time.
- `sakura-memory add user|notes "<fact>"`, `replace <store> "<part of old>" "<new>"`, `remove <store> "<part>"`, `show`. A full store refuses the write and lists what's in it: remove or merge something, then retry.
- `sakura-recall "<words>"` searches past conversations.
- "forget X" → `sakura-memory remove`. Secrets are refused.

## Big jobs
Run one job in a fresh context, with no quoting to get wrong:
```
sakura-worker <<'JOB'
verify: <command that exits 0 only if it worked>
scope: <files it may change>

<the brief>
JOB
```
It passes only if the verify command exits 0, it retries once with the failure, and it returns a short report. Run one at a time.

## Skills
Skills hold the procedures and tool lists for specialist work (pentesting, reversing, forensics, media, image
generation, databases, …). Load the matching skill before starting such a task.
