---
name: xlsx
description: Create, read and edit Excel spreadsheets (.xlsx); turn a CSV into a real spreadsheet with headers, types, formulas and formatting
---

Work with real spreadsheet files, not just print tables. Python is the tool.

Install on demand: `uv tool install --with openpyxl --with pandas openpyxl` is awkward; instead
`python3 -m pip install --user openpyxl pandas` or run via `uv run --with openpyxl --with pandas python3 - <<'PY' ...`.
Prefer `uv run --with openpyxl --with pandas python3 SCRIPT` so nothing pollutes the system Python.

Common jobs:
- **CSV -> spreadsheet:** read the CSV with pandas, infer/clean types, write `.xlsx` with openpyxl: bold header row,
  freeze the top row (`ws.freeze_panes = "A2"`), auto-width columns, number formats, and a total row with a real
  `=SUM(...)` formula (write the formula string, not the computed value, so it stays live).
- **Build from description:** create sheets, headers, formulas, simple charts (openpyxl `BarChart`/`LineChart`).
- **Edit existing:** `load_workbook(path)`, change cells/formulas, save. Preserve other sheets.

After writing, report the path and a one-line summary (sheets, rows, columns). Open it only if asked. Never fabricate
cell values from the source — read the real CSV/file.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder "<question>"` — hard code, algorithms or a tricky API.
