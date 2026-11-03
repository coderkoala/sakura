---
name: memory
description: Save a durable fact about the user when they say remember, note that, or commit to memory
---

When I say "remember", "note that", "commit to memory", or clearly state a lasting preference or fact about me, my
machines, or how I want you to work:

1. Distil it to one or two short, durable sentences — the fact itself, not the conversation around it. Resolve
   relative dates to absolute. Drop anything transient or secret (no passwords, keys, tokens).
2. Append it as a `- ` bullet to `~/.sakura/memories/MEMORY.md` (create the file if missing), each bullet on
   its own line. Read the file first and skip near-duplicates; update the existing line instead of adding a second.
3. Confirm in one line: `remembered: <the fact>`.

This is also picked up by the automatic memory pass, so over time the things you learn about me compound and you
become mine. Use what you remember without being asked. If I say "forget X", remove the matching bullet.
