---
name: notify
description: Send the user a desktop notification (and optionally a phone push) from scripts, jobs or long tasks
---

Use the `notify` helper (interpreter/bin/notify, on PATH): `notify "title" "body"`.
- Desktop: `notify-send` (libnotify; KDE/Wayland). Install: `sudo -A apt-get install -y libnotify-bin`.
- Phone push (optional): set `NTFY_TOPIC` (and `NTFY_SERVER`, default https://ntfy.sh) and it also POSTs to ntfy.
  For private push, self-host ntfy in Docker and point NTFY_SERVER at it.
Good for: "tell me when the long build finishes", mail-check alerts, a task that needs my input while I'm away.
Don't spam; one notification per meaningful event.
