---
name: rag
description: Semantic search over the user's own documents, notes and past work (local embeddings, no network)
---

Search the user's own documents with `rag`. Embeddings run locally on the CPU, and nothing leaves the machine.

- Index what the user names: `rag index ~/docs`. It handles text, code, markdown, PDF and .docx, skips secrets and generated folders, and only re-reads what changed.
- Search: `rag search "how does the cargo desk flow work" -k 6`, which prints each passage with its file and line.
- `rag status` shows what's indexed, and `rag forget PATH` removes something.

Use it for "where did I write X", and to ground an answer in the user's actual documents. Cite the file you used. If it finds nothing, say that instead of guessing.

## Specialist model
Only qwen3.5 drives this session (it's the one model here that tool-calls). For a hard sub-problem, pull a specialist one-shot and act on its answer yourself — you keep the tools:
- `consult coder "<question>"` — hard code, algorithms or a tricky API.
