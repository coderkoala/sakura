---
name: credentials
description: Store and read secrets (email passwords, API tokens, keys) with pass, the GPG-backed Unix password store
---

Secrets live in `pass` (passwordstore.org): GPG-encrypted files under ~/.password-store, scriptable, no daemon.

Setup (once): `sudo -A apt-get install -y pass`; needs a GPG key — if `gpg --list-secret-keys` is empty, create one
(`gpg --batch --quick-generate-key "$USER" default default never`), then `pass init <KEY-ID or email>`.

Use:
- store:  `pass insert -m email/outlook` (reads value from stdin; use -m for multiline like IMAP/SMTP blocks)
- read:   `pass show email/outlook`  (first line = the password; good for piping)
- list:   `pass ls`
- gen:    `pass generate service/name 24`

Convention: email creds at `email/<account>` with lines `password: ...`, `imap_host: ...`, `smtp_host: ...`.
Never print a secret into chat or a file; pass it directly to the tool that needs it. The `email` and mail-check
tools read from here.
