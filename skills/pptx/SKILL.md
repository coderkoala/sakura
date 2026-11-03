---
name: pptx
description: Create and edit PowerPoint presentations (.pptx) from an outline, notes or a document
---

Make real slide decks with python-pptx: `uv run --with python-pptx python3 SCRIPT`.

- From an outline/markdown: one slide per top-level point; title + bullet body using a bullet placeholder. Keep
  bullets short; push detail into speaker notes (`slide.notes_slide.notes_text_frame.text`).
- Use a clean layout: title slide, then "Title and Content" (layout index 1). Consistent fonts/sizes.
- Images/charts: `add_picture`, or native charts via `add_chart` with `CategoryChartData`.
- Edit existing: `Presentation(path)`, change shapes/text, save.
- A fast path for simple decks from markdown is pandoc: `pandoc in.md -o out.pptx`.

Report the path and slide count. Don't invent content the source didn't give; ask or mark gaps.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder "<question>"` — hard code, algorithms or a tricky API.
