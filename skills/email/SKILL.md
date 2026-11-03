---
name: email
description: Read, search, and send email over IMAP/SMTP with himalaya; credentials come from pass
---

Email is `himalaya` (a single Rust binary, IMAP+SMTP, JSON output). Install on demand: grab the latest
`himalaya-x86_64-linux` release into ~/.local/bin (`sudo -A apt-get` has no package), or `cargo install himalaya`.

Config at ~/.config/himalaya/config.toml, one block per account, password via a command so it stays in pass:
```toml
[accounts.outlook]
email = "you@outlook.com"
backend.type = "imap"
backend.host = "outlook.office365.com"
backend.port = 993
backend.login = "you@outlook.com"
backend.passwd.cmd = "pass show email/outlook"
message.send.backend.type = "smtp"
message.send.backend.host = "smtp.office365.com"
message.send.backend.port = 587
message.send.backend.login = "you@outlook.com"
message.send.backend.passwd.cmd = "pass show email/outlook"
```
Use (`-o json` for anything you need to parse):
- list/search: `himalaya envelope list -o json`, `himalaya envelope list -- FROM prof@uni.edu`
- read:        `himalaya message read <ID> -o json`
- send:        `himalaya message send < rfc822.txt`  (or `template send`)
- reply/fwd/move/flag: `himalaya message reply <ID>`, `... flag add <ID> seen`

Reading/searching mail is routine; sending is outward-facing — show me the full draft and get my `j` before
`send`. Never dump raw passwords; the passwd.cmd keeps them in pass.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder-fast "<question>"` — a quick snippet or one-off command.
