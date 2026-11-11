---
name: email
description: Read, search, and send email over IMAP/SMTP with himalaya; credentials come from pass
---

Email is `himalaya`. Set it up with `sakura-mail-setup install`, then `sakura-mail-setup account NAME EMAIL IMAP_HOST SMTP_HOST`. Passwords stay in pass and the user types them in, never you: tell them to run `pass insert email/NAME`. Prove it with `sakura-mail-setup check NAME`. `sakura-mail-setup notify on` adds a notification for new mail. Providers vary: Gmail and many others need an app password, and a provider that only allows OAuth, as Outlook.com does, needs himalaya's OAuth settings, which this setup doesn't write.

Add `--json` to anything you need to parse, and `-a NAME` to pick an account:

- list: `himalaya envelope list --page-size 20`, or `-m Sent` for another mailbox
- read: `himalaya message read <ID>`
- send: `himalaya message compose --to a@b.c --subject "..." --body "..." --send`
- reply: `himalaya message reply <ID> --body "..." --send`, and `himalaya message forward <ID> --to a@b.c --send`
- without `--send`, those print the message instead of sending it, which is how to show a draft
- flags and folders: `himalaya flag --help`, `himalaya message move --help`

Before you draft, run `pa voice`: if the user has learned their voice (`pa voice learn`, counted from their own sent mail), write the draft with their greeting, their sign-off, their length and tone. "Write like me" or "learn how I write" means `pa voice learn`. `sakura-recall "words"` finds old mail alongside past sessions and documents.

Reading and searching mail is routine. Sending is outward-facing: show the user the full draft and get their approval before you send. A worker can't send at all. Passwords stay in pass, so never print one.

## Specialist model

Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:

- `consult coder-fast "<question>"` — a quick snippet or one-off command.
