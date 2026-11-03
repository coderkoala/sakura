---
name: docx
description: Create and edit Word documents (.docx), and spellcheck/grammar-correct writing step by step
---

Two jobs: produce/edit Word files, and proofread the user's writing interactively.

**Word files** — `uv run --with python-docx python3 SCRIPT` (module import name is `docx`).
- Build from markdown/plain text: headings (`add_heading`), paragraphs, bullet/number lists, tables
  (`add_table`, style "Light Grid Accent 1"), page breaks (`add_page_break`), images (`add_picture`).
- Edit existing: `Document(path)`, modify runs/paragraphs, save. Keep existing styles.
- From markdown it is often fastest to go through pandoc: `pandoc in.md -o out.docx` (install `pandoc`).

**Spellcheck / grammar, step by step** (the "correct me" flow):
- Tools (install on demand): `hunspell hunspell-en-us` (fast spell), or LanguageTool for grammar
  (`uv tool install language-tool-python` then use it from Python, downloads a local LT the first run; fully offline
  after). For other languages add the matching hunspell dict (e.g. `hunspell-ne` for Nepali).
- Step-by-step means: find the issues, then walk them ONE AT A TIME — show the sentence, the problem, and the fix,
  and apply it on the user's approval (that is what `j`/`k` are for) before moving to the next. Do not silently
  rewrite the whole document. Explain each correction in a few words so the user learns.
- Keep the user's voice; fix errors, don't restyle their writing unless asked.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder "<question>"` — hard code, algorithms or a tricky API.
