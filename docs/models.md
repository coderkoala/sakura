# Which model runs

`sakura-model plan` says what this machine runs and why. Where the hardware allows, `?` drives with a 35B-A3B
Mixture-of-Experts model (abliterated, Q3_K_M): Ornith 1.5 by default since 0.9.5, Qwen3.6 before it. A model whose dense part and an expert cache sit in VRAM and whose other
experts stay in RAM, served by the `llama-server` that ships with Ollama. The VRAM budget is read from the machine, so
a desktop whose display holds VRAM gets a smaller cache. Anything else stays on the 9b on Ollama.

On a machine that qualifies, the install and the first start download it in the background with the other models
(15.6 GB, checksum verified). Until it's there, or if the server can't start, `?` falls back to the 9b.

Measured on an RTX 4060 Laptop with 32 GB RAM, RAM and budget as noted (`evals/bench_server.py`, `evals/run.py`):

|                            |           9b | Qwen3.6, 5.3 GB VRAM | Qwen3.6, 7.3 GB VRAM |
| -------------------------- | -----------: | -------------------: | -------------------: |
| Writing, warm              |     43 tok/s |             50 tok/s |             72 tok/s |
| Writing after a 26K prompt |              |             31 tok/s |             37 tok/s |
| Reading a long prompt      | ~2,000 tok/s |            503 tok/s |            584 tok/s |

The lower budget stands in for a 6 GB card by limiting the cache; it hasn't run on a real one. Other models loaded by
`consult` compete for the same VRAM while this server is awake (it leaves VRAM after 20 idle minutes and reuses the system
prompt's KV cache between turns).

**The fast tier.** `SAKURA_FAST=1 ?` runs Spark-X2.6 4B (abliterated, Q8, 4.4 GB): 28/30 on `evals/run.py` at a median of 8 seconds a case, measured 2026-11-08, against the 9b's 30/31. It makes real tool calls through the engine. As a worker it scored wall 24/28 and pa 65/66 (the 9b: 27/28 and 66/66), with the misses being attacks it declined to run rather than holes, so the 9b stays the fallback for now.

**Choosing every model.** `sakura-model pick` lists each job — the agent, the fast tier, `look`'s eyes, `rag`'s embeddings, the five `consult` roles and the GPU driver — with the model doing it and whether it's yours or Sakura's default. `sakura-model pick vision` opens a menu: what's been tried with Sakura, what Ollama already has, and (after asking, since it sends your RAM and VRAM and nothing else) whatmodel.sh's ranking for this machine; an entry without an Ollama tag is looked up on Hugging Face as a GGUF. Any Ollama tag or `hf.co/…` works, and `sakura-model pick driver hf.co/OWNER/REPO:FILE.gguf` takes a GGUF of your own for the driver, its checksum pinned on the first download. Nothing is refused: a stock model gets a one-line note that it may decline things, an untested agent a pointer to `evals/run.py`. The choice lives in `~/.sakura/models.json`; an environment variable still wins for one run. Every tool reads it through `lib/sakura_choices.py`, and a picked chat model gets an entry in a catalog the launcher passes, so it runs with Sakura's prompt and a 32K context (that also fixed the fast tier, which had been running without Sakura's prompt).

**Choosing a driver.** `sakura-model driver` lists the driver files Sakura knows, all the same shape (35B MoE, 3B active,
Q3_K_M, abliterated), so the VRAM budget holds for each. Measured 2026-11-08 on the same card and budget:

|                            | Qwen3.6 35B-A3B (`qwen36`) | Ornith 1.5 35B-A3B (`ornith15`, default) |
| -------------------------- | -------------------------: | ---------------------------------------: |
| `evals/run.py`             |                      30/31 |                                    30/30 |
| `evals/wall.py`            |                      27/28 |                                    27/28 |
| Writing, warm              |                   72 tok/s |                                 63 tok/s |
| Writing after a 26K prompt |                   37 tok/s |                                 26 tok/s |
| Reading a long prompt      |                  584 tok/s |                                509 tok/s |

Ornith gets everything right and is about a sixth slower; `sakura-model driver qwen36` is one command if speed matters more. `sakura-model pull` fetches whichever is chosen;
`sakura-model advise` asks whatmodel.sh what fits this RAM and VRAM, sending only those two numbers and only when you run
it. A higher score isn't a better Sakura until the model calls tools in the qwen-code shape and passes `evals/run.py`.
