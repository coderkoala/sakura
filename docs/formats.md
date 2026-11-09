# On-disk formats and the compatibility promise

Sakura accumulates state the user would hate to lose. These rules hold from 0.9.7:

1. **The shapes below are v1, with or without a `v` field.** Existing stores stay as they are; stores born after 0.9.7 carry `"v": 1`. Readers never crash on either.
2. **Readers ignore fields they don't know.** New code may add fields; old code keeps working past them.
3. **A field, once shipped, keeps its name and meaning.** Renames happen by adding the new field and reading both for two releases.
4. **A breaking change bumps `v`**, and the reader that bumps it migrates the old shape in place, once, keeping a `.bak` next to it.
5. **Plain-text stores (memory, `.sakura.md`, decisions.jsonl lines) never get structure added** that a human couldn't have typed.

| Store | Path | Shape |
|---|---|---|
| pa schedule | `~/.sakura/pa/schedule.json` | a list of `{id, kind: reminder\|job\|watch\|command\|mail, at, rule, …}` |
| pa offers | `~/.sakura/pa/offers.json` | list of `{id, text, command, cwd, expires, done?}` |
| pa settings | `~/.sakura/pa/settings.json` | flat keys; `mail_rules: {urgent: [], mute: []}` |
| night shift | `~/.sakura/tonight/queue.json` | `{at, seq, jobs: [{id, dir, settings, brief, status, …}]}` |
| guardian | `~/.sakura/guardian/config.json`, `seen.json`, `disk.jsonl` | `{backups: {name: {path, every, restored?}}, certs?}`; seen: text→epoch; disk: one `{t, d}` per line |
| downloads | `~/.sakura/dl/queue.json` | `{v, items: [{id, url, file, total, state, sha256?, checksum?}]}` |
| logs mutes | `~/.sakura/logs-mutes.json` | `{v, items: [{pattern, added, hits}]}` |
| drive syncs | `~/.sakura/drive/syncs.json` | list of `{id, src, dest, until, pid, started}` |
| torrents | transmission's own config dir | transmission's format, not ours |
| backups | `~/.sakura/backup/NAME.json` + `NAME.pass` (0600) | `{v, dest, sources, excludes}`; the password file is sacred |
| procwatch | `~/.sakura/procs/NAME.json` | `{pid, command, cwd, started}` |
| vid archives | `~/.sakura/vid/NAME.json`, `NAME.archive`, `NAME.log` | `{v, name, url, dir, runs, started, finished, rc, before, after, new, pid}`; the `.archive` is yt-dlp's own `extractor id` per line |
| vid watches | `~/.sakura/vid/NAME.seen.json` | `{v, url, ids: [], checked}` — the video ids already shown as new |
| decisions | `~/.sakura/decisions.jsonl` | one `{when, text, dir, repo, branch, commit}` per line, append-only |
| memory | `~/.sakura/memory/*.md` | plain text, one fact per line, synced through dotfiles |
| undo store | `~/.sakura/undo/` | managed by the root-owned guard; its format changes only with a guard release |
| recall index | `~/.cache/sakura/recall.db` | a cache: safe to delete, rebuilt on next use |
| kept tools | `~/.sakura/tools/{bin,meta}` | the script plus `{about, check}`; the check re-proves it on any machine |

Caches (`~/.cache/sakura/*`) carry no promise: deleting them costs a rebuild, nothing else.
