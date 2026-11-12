<div align="center">

# 🌸 Sakura

### Claude Code at home — a fully-local, uncensored terminal agent that acts.

[![Platform](https://img.shields.io/badge/platform-Linux-1793D1?logo=linux&logoColor=white)](#install)
[![Models](<https://img.shields.io/badge/models-local%20(Ollama)-000000?logo=ollama&logoColor=white>)](docs/models.md)
[![Privacy](https://img.shields.io/badge/data-stays%20on%20my%20machine-2ea44f)](docs/trust-boundary.md)
[![License](https://img.shields.io/badge/license-MIT-black)](LICENSE)

**[Features](docs/features.md)** · **[Models](docs/models.md)** · **[Trust boundary](docs/trust-boundary.md)** · **[Evals](docs/evals.md)** · **[Roadmap](ROADMAP.md)**

_by [Nobel Dahal](https://github.com/coderkoala)_

</div>

---

I live in the terminal across seven-plus machines, and I wanted an agent that _does the work_ without shipping
my keystrokes to someone else's cloud, without refusing my own authorised security work, and without a
per-token bill. Sakura runs on my own hardware with local models, on an 8 GB GPU, and it is mine to shape.

```console
$ make test                              # something breaks
$ ?fix                                   # finds the cause, fixes it, reruns the command to prove it
$ ?undo                                  # puts back everything that turn changed
$ ?tour ~/code/some-repo                 # any codebase in five minutes, a file:line for every claim
$ ?recall nginx 502                      # past sessions, shell history, decisions, documents, mail
$ ?on starlight show me the errors as a table
$ ?what "merge two pdfs"                 # names the command, no model:  conv merge a.pdf b.pdf
$ ?recap yesterday                       # what it did, from the record, not from a model
```

## What you get

- **An agent that acts, and a way back.** It runs commands, edits files and chains steps without stopping to
  ask. A guard snapshots before anything writes, so `?undo` restores it and `?recap` shows exactly what ran.
  [The keys →](docs/features.md#the-keys)
- **Local and private.** Models run on your GPU; search, document retrieval, OCR, speech and the browser run
  on your machine. No account, no API key, no telemetry.
  [Which model runs →](docs/models.md)
- **Current, with sources.** Time-sensitive questions are looked up before the model answers, and every
  answer carries its source and date. [Knowledge and the web →](docs/features.md#knowledge-and-the-web)
- **A trust boundary.** Fetched content is scanned and fenced as data, and sending data to a host you never
  named always stops for approval. [How it works →](docs/trust-boundary.md)
- **Work while you sleep.** A coordinator hands jobs to sandboxed workers that pass only when your verify
  command exits 0; `?tonight` queues them for the night and shows you the diffs in the morning.
  [The agent →](docs/features.md#the-agent)
- **A toolkit that needs no model.** Convert, merge, redact and sign files; query CSVs with SQL; see ports,
  disk, logs and drift across your machines; reminders that fire once across all of them.
  [Files →](docs/features.md#files-and-paperwork) · [Machines →](docs/features.md#your-machines) ·
  [Reminders →](docs/features.md#reminders-phone-and-mail)
- **39 specialist skills.** Office documents, security, OSINT, reversing, forensics, networking, databases,
  media and translation, each with its own curated sources.

The rules it's built on: **yours** (runs on your hardware), **proven, not claimed** (a feature is done when a
check says so), **human work stays human** (CAPTCHAs, passwords and sends come to you), and **mechanics over
prompts** (when the model keeps getting something wrong, change what's possible).

## Install

Linux with an NVIDIA GPU (8 GB of VRAM and up; smaller cards are untested), Python 3.11+, git and
[Ollama](https://ollama.com/download).

```bash
git clone https://github.com/coderkoala/sakura && cd sakura
./install.sh        # starts the model downloads and tells you what's still missing
sakura-launch
```

Models that suit the machine download in the background; `sakura-model plan` says what yours will run and
`sakura-doctor` checks the install is whole. The engine comes from the release; to build it yourself see
[patches/README.md](patches/README.md). Your own notes for the agent go in `~/.config/sakura/profile.md`.

## Docs

| | |
| --- | --- |
| [Features](docs/features.md) | Everything it does, grouped by what you'd reach for it for |
| [Models](docs/models.md) | Which model runs on which hardware, measured, and how to choose your own |
| [Trust boundary](docs/trust-boundary.md) | The threat model for untrusted content, and its limits |
| [Evals](docs/evals.md) | One eval per feature, graded by real state, and how to run them |
| [Formats](docs/formats.md) | What's kept under `~/.sakura`, with a compatibility promise |
| [Roadmap](ROADMAP.md) | Where it stands, what's proven, what comes next |
| [Everything](docs/everything.md) | The map behind the roadmap: each want and the local tool or model that serves it |
| [Real-world passes](docs/real-world.md) | Checklists for what the evals can't reach: real mail, a real CAPTCHA, a second machine |

## Layout

| Path | What it is |
| --- | --- |
| `bin/` | Every command. Each one's `--help` is its manual; the key list is the header of `shell/sakura.bash` |
| `hooks/`, `rules/` | Grounding, the guard, the egress guard, undo snapshots; the exec-policy and egress allowlist |
| `skills/`, `prompts/`, `AGENTS.md` | The specialist skills and the agent's instructions |
| `mcp/sakura-web/` | Web knowledge: search, fetch, the injection detector, curated sources |
| `evals/` | The proof |

## Credit

Sakura is my fork of [Open Interpreter](https://github.com/OpenInterpreter) (the Rust `codex-rs` engine); the
binary is built from that fork. Everything in this repo — the rules, the tools, the skills, the branding — is
mine. MIT licensed.
