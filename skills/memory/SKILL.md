---
name: memory
description: Save, change or forget a durable fact when the user says remember, note that, commit to memory or forget
---

Use `sakura-memory`. Don't edit its files.

1. Boil it down to one short sentence: the fact, not the conversation. Turn relative dates into absolute ones.
2. Save it: `sakura-memory add user "<fact>"` for who the user is and how they work, `sakura-memory add notes "<fact>"` for machines, projects and lessons learned.
3. If the store is full, it refuses and lists what's there. Remove what no longer matters, or `replace` two facts with one, then add again.
4. Confirm in one line: `remembered: <the fact>`.

To change a fact: `sakura-memory replace <store> "<unique part of it>" "<new fact>"`. For "forget X": `sakura-memory remove <store> "<unique part>"`.

It doesn't belong in memory if it's:
- a secret (these are refused)
- progress on the current task
- a step-by-step procedure (that's a skill)
- something a command or the repo can tell you

Saved facts reach the prompt at the next session. They're on disk straight away.
