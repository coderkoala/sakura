---
name: email
description: Read, search, and send email over IMAP/SMTP with himalaya; credentials come from pass
---

Email is `himalaya`. Set it up with `sakura-mail-setup install`, then `sakura-mail-setup account NAME EMAIL IMAP_HOST SMTP_HOST`. Passwords stay in pass and the user types them in, never you: tell them to run `pass insert email/NAME`. Prove it with `sakura-mail-setup check NAME`.

Use (`-o json` for anything you need to parse):
- list/search: `himalaya envelope list -o json`, `himalaya envelope list -- FROM prof@uni.edu`
- read:        `himalaya message read <ID> -o json`
- send:        `himalaya message send < rfc822.txt`  (or `template send`)
- reply/fwd/move/flag: `himalaya message reply <ID>`, `... flag add <ID> seen`

Reading/searching mail is routine; sending is outward-facing — show the user the full draft and get their approval before
`send`. A worker can't send at all. Never dump raw passwords; the passwd.cmd keeps them in pass.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder-fast "<question>"` — a quick snippet or one-off command.
