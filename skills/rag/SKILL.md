---
name: rag
description: Semantic search over the user's own documents, notes and past work (local embeddings, no network)
---

Local RAG: embeddings from Ollama `qwen3-embedding:0.6b` (already pulled), stored in a single sqlite-vec DB at
~/.local/share/rag/index.db. No server. Exposed to you as the MCP tool `rag_search` once wired; the `rag` CLI
(interpreter/bin/rag) does the same from the shell.

- index a folder: `rag index ~/mis/docs`   (chunks text/markdown/pdf-text, embeds, upserts)
- search:         `rag search "how does the cargo desk flow work" -k 6`  -> file:chunk + text
Use it when a persona needs reference the model doesn't carry: kb/research questions, "where did I write X",
grounding an answer in the user's actual docs. Always cite the file path you used; say so when nothing matches
rather than inventing. Re-index after big doc changes.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder "<question>"` — hard code, algorithms or a tricky API.
