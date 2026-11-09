---
name: pdf
description: Turn markdown/HTML into a clean PDF whose page breaks never split a table, list, figure or heading-from-its-text
---

For merging, splitting, page picks, rotating, compressing, OCR, unlocking and metadata stripping, `conv merge|split|pages|
rotate|compress|ocr|unlock|strip X.pdf` does it locally (qpdf, ghostscript, ocrmypdf); `conv FILE --to pdf` for office files.
Never send a PDF to a website for any of this.

Produce PDFs where layout is respected across page breaks. Preferred engine: WeasyPrint (HTML/CSS, honours CSS
fragmentation) or Typst (fast, no LaTeX). Install on demand.

**Markdown -> PDF with safe page breaks (WeasyPrint):**
1. `uv tool install weasyprint` (and `pandoc` via apt).
2. `pandoc input.md -t html5 --standalone --metadata title="..." -o /tmp/doc.html`
3. Inject CSS so breaks don't split things, then render:
   ```css
   @page { size: A4; margin: 2cm; }
   table, figure, pre, blockquote { break-inside: avoid; }
   tr, li { break-inside: avoid; }
   h1,h2,h3,h4 { break-after: avoid; }      /* keep a heading with its following text */
   ul, ol { break-inside: avoid-page; }      /* keep short lists whole; long lists still flow */
   ```
   `weasyprint /tmp/doc.html out.pdf -s breaks.css`
4. If a list or table is legitimately longer than a page, `break-inside: avoid` can't keep it whole — WeasyPrint will
   break it at a row/item boundary (never mid-row). Tell the user when that happens rather than overflowing.

**Alternative (Typst):** install the `typst` release binary; `pandoc input.md -o out.pdf --pdf-engine=typst`. Typst
keeps list items and table rows intact by default and is much faster than LaTeX.

Verify the PDF was written (page count via `pdfinfo` from `poppler-utils`) and report the path. For an existing PDF
that already splits badly, re-render from its source; don't try to re-paginate a finished PDF.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder "<question>"` — hard code, algorithms or a tricky API.
