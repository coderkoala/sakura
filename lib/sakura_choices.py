#!/usr/bin/env python3
"""Which model does each job — the one place that answers it. Every tool that loads a model asks here.

Order, for every role: the role's environment variable (for one run), then the user's choice in ~/.sakura/models.json
(`sakura-model pick`), then Sakura's default. The file is {"v": 1, "roles": {ROLE: TAG}, "drivers": {NAME: {...}}}.

  python3 lib/sakura_choices.py get ROLE      the model for ROLE (what sakura-launch reads)
  python3 lib/sakura_choices.py catalog       write ~/.sakura/catalog.json covering every chat model in use, print its path
"""

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
HOME = os.environ.get("SAKURA_HOME", os.path.expanduser("~/.sakura"))
FILE = os.path.join(HOME, "models.json")
CATALOG = os.path.join(HOME, "catalog.json")

# role: (environment variable, Sakura's default, what it's for, kind). kind "chat" runs a session and needs a catalog entry.
ROLES = {
    "agent": (
        "SAKURA_BIG_MODEL",
        "huihui_ai/qwen3.5-abliterated:9b",
        "the agent when the GPU driver can't run, and the intent check",
        "chat",
    ),
    "fast": (
        "SAKURA_FAST_MODEL",
        "hf.co/FrostWolfAI/Spark-X2.6-4B-abliterated-GGUF:Q8_0",
        "SAKURA_FAST=1 sessions",
        "chat",
    ),
    "vision": (
        "SAKURA_VISION_MODEL",
        "huihui_ai/qwen2.5-vl-abliterated:3b",
        "look: images, screenshots, scans",
        "vision",
    ),
    "embed": (
        "SAKURA_RAG_MODEL",
        "qwen3-embedding:0.6b",
        "rag search (changing it means `rag index` again)",
        "embed",
    ),
    "coder": (
        "SAKURA_CONSULT_CODER",
        "huihui_ai/qwen2.5-coder-abliterate:14b",
        "consult coder: hard code, algorithms",
        "consult",
    ),
    "coder-fast": (
        "SAKURA_CONSULT_CODER_FAST",
        "huihui_ai/qwen2.5-coder-abliterate:3b",
        "consult coder-fast: quick snippets",
        "consult",
    ),
    "reason": (
        "SAKURA_CONSULT_REASON",
        "huihui_ai/qwen2.5-abliterate:14b",
        "consult reason: deeper analysis",
        "consult",
    ),
    "security": (
        "SAKURA_CONSULT_SECURITY",
        "WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-8B:latest",
        "consult security",
        "consult",
    ),
    "prose": (
        "SAKURA_CONSULT_PROSE",
        "thomboe/dolphin3.0-llama3.1-8b-abliterated:latest",
        "consult prose: writing",
        "consult",
    ),
}
# What's been tried with Sakura, per role, offered first by the picker. "tested" means an eval here passed with it.
KNOWN = {
    "agent": [
        ("huihui_ai/qwen3.5-abliterated:9b", "tested: run 30/31, wall 27/28"),
        (
            "huihui_ai/qwen3.5-abliterated:2b",
            "tested: guessed wrong tool names; only for 4 GB",
        ),
    ],
    "fast": [
        (
            "hf.co/FrostWolfAI/Spark-X2.6-4B-abliterated-GGUF:Q8_0",
            "tested: run 28/30, median 8 s a case",
        )
    ],
    "vision": [
        ("huihui_ai/qwen2.5-vl-abliterated:3b", "tested: look OCR and vision checks"),
        ("qwen3-vl:4b", "2026: DocVQA-class reading, ~3 GB"),
        ("qwen3-vl:8b", "2026: best open Devanagari reading, ~6 GB"),
        ("gemma4:e4b", "2026: general vision"),
        ("glm-ocr", "2026: documents, 0.9B"),
    ],
    "embed": [
        ("qwen3-embedding:0.6b", "tested: rag eval"),
        ("bge-m3", "Hindi and other Indic text"),
        ("qwen3-embedding:4b", "better recall, 2.5 GB"),
    ],
    "coder": [("huihui_ai/qwen2.5-coder-abliterate:14b", "the default")],
    "coder-fast": [("huihui_ai/qwen2.5-coder-abliterate:3b", "the default")],
    "reason": [
        ("huihui_ai/qwen2.5-abliterate:14b", "the default"),
        ("gpt-oss:20b", "2026: strong reasoning, 3.6B active"),
    ],
    "security": [
        ("WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-8B:latest", "the default")
    ],
    "prose": [("thomboe/dolphin3.0-llama3.1-8b-abliterated:latest", "the default")],
}


def load():
    try:
        d = json.load(open(FILE))
        if isinstance(d, dict):
            d.setdefault("v", 1)
            d.setdefault("roles", {})
            d.setdefault("drivers", {})
            return d
    except (OSError, ValueError):
        pass
    return {"v": 1, "roles": {}, "drivers": {}}


def save(d):
    os.makedirs(HOME, exist_ok=True)
    tmp = FILE + ".tmp"
    json.dump(d, open(tmp, "w"), indent=1)
    os.replace(tmp, FILE)


def get(role):
    env, default, _, _ = ROLES[role]
    if os.environ.get(env):
        return os.environ[env]
    return load()["roles"].get(role) or default


def source(role):
    env = ROLES[role][0]
    if os.environ.get(env):
        return f"${env}"
    return "yours" if load()["roles"].get(role) else "default"


def catalog():
    """The repo's catalog plus an entry for every chat model in use, so a model you picked still gets Sakura's prompt and the
    right context window. Written only when it differs, so the engine sees a stable file."""
    base = json.load(open(os.path.join(ROOT, "models.json")))
    have = {m["slug"] for m in base["models"]}
    template = next(m for m in base["models"] if m["slug"] == ROLES["agent"][1])
    extra = []
    for role, (_, _, _, kind) in ROLES.items():
        if kind != "chat":
            continue
        slug = get(role)
        if slug in have:
            continue
        e = copy.deepcopy(template)
        e["slug"] = slug
        e["display_name"] = slug.split("/")[-1]
        e["description"] = (
            f"Picked for {role} (sakura-model pick); Sakura's prompt and a 32K context."
        )
        extra.append(e)
        have.add(slug)
    out = {**base, "models": base["models"] + extra}
    text = json.dumps(out, indent=1)
    os.makedirs(HOME, exist_ok=True)
    try:
        if open(CATALOG).read() == text:
            return CATALOG
    except OSError:
        pass
    open(CATALOG + ".tmp", "w").write(text)
    os.replace(CATALOG + ".tmp", CATALOG)
    return CATALOG


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "get" and a[1] in ROLES:
        print(get(a[1]))
    elif a == ["catalog"]:
        print(catalog())
    else:
        print(__doc__)
        sys.exit(2)
