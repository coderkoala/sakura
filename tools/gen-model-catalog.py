#!/usr/bin/env python3
"""Generate sakura/models.json — a model catalog for the local Ollama models.

Why: codex-rs has no built-in metadata for `huihui_ai/qwen3.5-abliterated:*`, so at
startup it warns "Model metadata ... not found. Defaulting to fallback metadata; this
can degrade performance" and uses a fallback that assumes a 272k-token context window.
Supplying a catalog (config.toml `model_catalog_json`) marks the models known: the
warning goes away and the context window is stated correctly (32768, matching
OLLAMA_CONTEXT_LENGTH) instead of guessed.

The entries mirror the values codex-rs itself uses for an unknown local slug
(shell_type=default, web_search=text, no reasoning levels, truncation bytes/10000).

`base_instructions` is Sakura's own prompt (prompts/base.md). With harness = "qwen-code" the
harness supplies the tool-usage prompt and appends base_instructions LAST as "Session
Instructions", so this is the final, overriding word — Nobel's philosophy and the local model's
failure modes, ~1.1k tokens. (It used to embed Codex's 20 KB prompt.md: a second, conflicting
agent prompt teaching tools this harness doesn't expose.) If you ever switch the harness off,
this short prompt would be the ONLY system prompt — regenerate from prompt.md instead.

Regenerate after editing the prompt:
    python3 tools/gen-model-catalog.py prompts/base.md > models.json
"""
import json
import os
import sys

# Slugs Sakura can run (config.toml `model` + `default_subagent_model`, and /model targets).
MODELS = [
    ("huihui_ai/qwen3.5-abliterated:9b", "Qwen3.5 Abliterated 9B"),
    ("huihui_ai/qwen3.5-abliterated:2b", "Qwen3.5 Abliterated 2B"),
]
CONTEXT_WINDOW = 32768  # keep in step with OLLAMA_CONTEXT_LENGTH and config.toml model_context_window


def entry(slug, name, base_instructions):
    # Fields with no serde default in codex-rs ModelInfo must be present; the rest default.
    # Values match codex-rs's own fallback for an unknown local slug (model_info_from_slug).
    return {
        "slug": slug,
        "display_name": name,
        "description": "Local uncensored generalist on Ollama (8 GB tier).",
        "base_instructions": base_instructions,
        "supported_reasoning_levels": [],
        "shell_type": "default",
        "visibility": "none",
        "supported_in_api": True,
        "priority": 99,
        "availability_nux": None,
        "upgrade": None,
        "support_verbosity": False,
        "default_verbosity": None,
        "apply_patch_tool_type": None,
        "web_search_tool_type": "text",
        "truncation_policy": {"mode": "bytes", "limit": 10000},
        "context_window": CONTEXT_WINDOW,
        "max_context_window": CONTEXT_WINDOW,
        "experimental_supported_tools": [],
    }


def main():
    prompt_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "prompts", "base.md"
    )
    try:
        base = open(prompt_path, encoding="utf-8").read()
    except OSError as e:
        sys.exit(f"cannot read the base prompt at {prompt_path}: {e}\n"
                 f"pass a prompt file path as arg 1 (default: prompts/base.md).")
    catalog = {"models": [entry(s, n, base) for s, n in MODELS]}
    json.dump(catalog, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
