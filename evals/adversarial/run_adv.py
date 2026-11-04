#!/usr/bin/env python3
"""Adversarial intent-vs-input runner for hooks/intent.py + hooks/web_ground.py.

For each case: classify with the router (same model the hook uses), run the full hook, sort what
got injected into kinds, grade intent / entities / harmful injection. Writes results.json.
  python3 evals/adversarial/run_adv.py [--only id,id]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import intent  # noqa: E402

MODEL = "huihui_ai/qwen3.5-abliterated:9b"

KINDS = [
    ("officeholder", re.compile(r"per Wikidata's current|head of (government|state) of|office-holder", re.I)),
    ("registry", re.compile(r"Latest published version of|exists in several registries|latest published version", re.I)),
    ("page", re.compile(r"already fetched for you", re.I)),
    ("wikipedia", re.compile(r"(^|\n)Wikipedia: ", re.I)),
    ("version_ctx", re.compile(r"Version context for this project", re.I)),
]

ROLE_SYN = {"pm": "prime minister", "premier": "prime minister", "head of government": "prime minister",
            "king": "monarch", "queen": "monarch", "head of state": "president"}


def norm(v):
    if v is None:
        return None
    v = str(v).strip().lower().replace("_", " ").replace("-", " ")
    return ROLE_SYN.get(v, v) or None


def ent_ok(field, want, got):
    w, g = norm(want), norm(got)
    if w is None:
        return g in (None, "", "null", "none")
    if g is None:
        return False
    if field == "ecosystem":
        return w == g
    return w == g or w in g or g in w


def run_hook(prompt, cwd):
    t = time.time()
    p = subprocess.run(["python3", os.path.join(ROOT, "hooks", "web_ground.py")],
                       input=json.dumps({"prompt": prompt, "cwd": cwd, "model": MODEL}),
                       capture_output=True, text=True, timeout=120)
    dt = time.time() - t
    ctx = ""
    try:
        ctx = json.loads(p.stdout or "{}").get("hookSpecificOutput", {}).get("additionalContext", "")
    except Exception:
        pass
    return ctx, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    cases = json.load(open(os.path.join(HERE, "cases.json")))["cases"]
    if a.only:
        want = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in want]
    results = []
    for i, c in enumerate(cases, 1):
        cwd = os.path.expanduser(c.get("cwd", "~"))
        t = time.time()
        got = intent.classify(c["prompt"], MODEL) or {}
        cls_s = time.time() - t
        ctx, hook_s = run_hook(c["prompt"], cwd)
        kinds = [k for k, rx in KINDS if rx.search(ctx)]
        exp = c["expected"]
        intent_ok = got.get("intent") == exp["intent"]
        ents = {f: ent_ok(f, exp[f], got.get(f)) for f in exp if f != "intent"}
        harmful = [k for k in kinds if k in c.get("harmful", [])]
        r = {"id": c["id"], "category": c["category"], "prompt": c["prompt"], "expected": exp, "got": got,
             "intent_ok": intent_ok, "entities_ok": all(ents.values()) if ents else True, "entity_detail": ents,
             "injected_kinds": kinds, "harmful": harmful, "injected": ctx[:300],
             "classify_s": round(cls_s, 1), "hook_s": round(hook_s, 1), "harm_if_wrong": c["harm_if_wrong"]}
        results.append(r)
        flag = ("OK " if intent_ok and r["entities_ok"] else "BAD") + (" HARM" if harmful else "")
        print(f"[{i:2d}/{len(cases)}] {flag:8s} {c['id']:28s} got={got.get('intent')}/{got.get('tool')}/"
              f"{got.get('subject')}/{got.get('role')} inj={kinds} {cls_s:.1f}s/{hook_s:.1f}s", flush=True)
    json.dump(results, open(os.path.join(HERE, "results.json"), "w"), indent=1, ensure_ascii=False)
    n = len(results)
    print(f"\nintent {sum(r['intent_ok'] for r in results)}/{n}  entities {sum(r['entities_ok'] for r in results)}/{n}  "
          f"harmful injections {sum(bool(r['harmful']) for r in results)}/{n}")


if __name__ == "__main__":
    main()
