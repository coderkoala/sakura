#!/usr/bin/env python3
"""The family-archive tools that lean on local models: faces, restore, conv subs, translate. Graded by planted images and files,
never by the tool's own words. A check whose model or driver isn't on this machine is SKIPPED and says why (it isn't a pass),
so the summary is honest about what was proven here.

  evals/archive.py              every case
  evals/archive.py --only NAME  one of: faces restore subs translate
faces needs insightface + onnxruntime + scikit-image (its bundled astronaut photo is the face); restore needs Vulkan for the real
run (the install path and dry runs are checked everywhere); subs needs a whisper model in ~/.cache/sakura/whisper or the network;
translate needs an Argos package or the network.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
SKIP = object()


def run(args, env=None, cwd=None, timeout=900, stdin=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(args, env=e, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=stdin)


def have(mod):
    return subprocess.run([sys.executable, "-c", f"import {mod}"], capture_output=True).returncode == 0


def faces(tmp):
    if not (have("insightface") and have("onnxruntime") and have("skimage")):
        return {"faces (insightface, onnxruntime, scikit-image not all installed)": SKIP}
    from PIL import Image
    import numpy as np
    from skimage import data
    lib = os.path.join(tmp, "lib", "trip")
    os.makedirs(lib)
    astro = Image.fromarray(data.astronaut())
    astro.save(os.path.join(lib, "eileen1.jpg"))
    astro.transpose(Image.FLIP_LEFT_RIGHT).resize((400, 400)).save(os.path.join(lib, "eileen2.jpg"))
    Image.fromarray(data.coffee()).save(os.path.join(lib, "coffee.jpg"))
    Image.fromarray(np.full((300, 300, 3), 120, np.uint8)).save(os.path.join(tmp, "lib", "wall.png"))
    env = {"SAKURA_FACES_DIR": os.path.join(tmp, "idx")}
    f = os.path.join(BIN, "faces")
    idx = run([f, "index", os.path.join(tmp, "lib")], env, timeout=1800)
    if idx.returncode == 3:
        return {"faces (model couldn't be fetched)": SKIP}
    people = json.loads(run([f, "people", "--json"], env).stdout or "[]")
    again = run([f, "index", os.path.join(tmp, "lib")], env)
    named = run([f, "name", str(people[0]["id"]), "Eileen"], env) if people else None
    found = json.loads(run([f, "find", "Eileen", "--json"], env).stdout or "[]") if people else []
    who = run([f, "who", os.path.join(lib, "eileen2.jpg")], env).stdout if people else ""
    nobody = run([f, "who", os.path.join(lib, "coffee.jpg")], env).stdout
    status = run([f, "status"], env).stdout
    index = json.load(open(os.path.join(tmp, "idx", "index.json")))
    return {"two photos of the same person become one cluster, the cup and the wall none": idx.returncode == 0 and len(people) == 1 and people[0]["photos"] == 2,
            "re-indexing skips what it has seen": "nothing new" in again.stdout,
            "a name sticks, find returns her photos best first": named is not None and named.returncode == 0 and {os.path.basename(x["path"]) for x in found} == {"eileen1.jpg", "eileen2.jpg"},
            "who names her in a photo, and finds nobody in the coffee": "Eileen" in who and "no faces" in nobody,
            "the signatures never leave the index file": "4 photos indexed" in status and all(len(x["emb"]) == 512 for x in index["faces"])}


def restore(tmp):
    r = os.path.join(BIN, "restore")
    env = {"SAKURA_RESTORE_DIR": os.path.join(tmp, "restore")}
    dry = run([r, "install", "--dry"], env)
    tools = run([r, "--tools"], env)
    from PIL import Image
    Image.new("RGB", (32, 32), "red").save(os.path.join(tmp, "p.jpg"))
    nothing = run([r, os.path.join(tmp, "p.jpg")], env)
    out = {"install names both GitHub releases and fetches nothing on --dry": dry.returncode == 0 and "Real-ESRGAN/releases" in dry.stdout and "rife-ncnn-vulkan/releases" in dry.stdout and not os.path.exists(os.path.join(tmp, "restore")),
           "--tools says what's missing; a run without the binary says how to get it": "missing" in tools.stdout and nothing.returncode == 3 and "restore install" in nothing.stderr}
    if shutil.which("vulkaninfo") and subprocess.run(["vulkaninfo", "--summary"], capture_output=True).returncode == 0 and os.environ.get("SAKURA_EVAL_NETWORK") == "1":
        inst = run([r, "install"], env, timeout=1200)
        up = run([r, os.path.join(tmp, "p.jpg"), "--scale", "2"], env, timeout=600)
        big = os.path.join(tmp, "p restored.jpg")
        out["a real upscale doubles the size (Vulkan present)"] = inst.returncode == 0 and up.returncode == 0 and os.path.exists(big) and Image.open(big).size == (64, 64)
    else:
        out["a real upscale (needs Vulkan and SAKURA_EVAL_NETWORK=1)"] = SKIP
    return out


def subs(tmp):
    c = os.path.join(BIN, "conv")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=64x64:rate=5", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", os.path.join(tmp, "c.mp4")], check=True)
    dry = run([c, "subs", os.path.join(tmp, "c.mp4"), "--dry"])
    out = {"subs --dry describes the whisper run and writes nothing": dry.returncode == 0 and "faster-whisper" in dry.stdout and not os.path.exists(os.path.join(tmp, "c.srt"))}
    cache = os.path.expanduser("~/.cache/sakura/whisper")
    if (os.path.isdir(cache) and os.listdir(cache)) or os.environ.get("SAKURA_EVAL_NETWORK") == "1":
        if shutil.which("say") or shutil.which("espeak-ng") or shutil.which("piper"):
            # a real sentence spoken by the local TTS, then transcribed: the words must come back
            wav = os.path.join(tmp, "s.wav")
            tts = shutil.which("espeak-ng")
            if tts:
                subprocess.run([tts, "-w", wav, "the quick brown fox jumps over the lazy dog"], check=False)
            if os.path.exists(wav):
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4", "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", os.path.join(tmp, "s.mp4")], check=False)
                r = run([c, "subs", os.path.join(tmp, "s.mp4"), "--model", "tiny", "--lang", "en"], timeout=1800)
                srt = open(os.path.join(tmp, "s.srt")).read().lower() if os.path.exists(os.path.join(tmp, "s.srt")) else ""
                out["a spoken sentence comes back as a timed .srt"] = r.returncode == 0 and "-->" in srt and "fox" in srt and "lazy" in srt
                return out
        out["a spoken sentence comes back as a timed .srt (needs espeak-ng to make the voice)"] = SKIP
    else:
        out["a spoken sentence comes back as a timed .srt (needs a whisper model or SAKURA_EVAL_NETWORK=1)"] = SKIP
    return out


def translate(tmp):
    t = os.path.join(BIN, "translate")
    if not have("argostranslate"):
        return {"translate (argostranslate not installed)": SKIP}
    langs = run([t, "langs"])
    installed = "en→hi" in langs.stdout.split("available")[0] or "en→ne" in langs.stdout.split("available")[0]
    if not installed and os.environ.get("SAKURA_EVAL_NETWORK") != "1":
        return {"translate (no package installed; SAKURA_EVAL_NETWORK=1 fetches en→hi)": SKIP}
    dst = "ne" if "en→ne" in langs.stdout.split("available")[0] else "hi"
    r = run([t, "Good morning, how are you?", "--to", dst, "--from", "en"], timeout=1200)
    open(os.path.join(tmp, "a.srt"), "w").write("1\n00:00:01,000 --> 00:00:02,000\nGood morning\n\n2\n00:00:03,000 --> 00:00:04,000\nThank you\n\n")
    s = run([t, os.path.join(tmp, "a.srt"), "--to", dst, "--from", "en"], timeout=600)
    srt = open(os.path.join(tmp, f"a.{dst}.srt")).read() if os.path.exists(os.path.join(tmp, f"a.{dst}.srt")) else ""
    import re
    return {"a sentence comes back in Devanagari": r.returncode == 0 and re.search(r"[ऀ-ॿ]", r.stdout) is not None,
            "an .srt keeps its numbering and timings, translates the lines": s.returncode == 0 and "00:00:01,000 --> 00:00:02,000" in srt and "Good morning" not in srt and re.search(r"[ऀ-ॿ]", srt) is not None}


CASES = {"faces": faces, "restore": restore, "subs": subs, "translate": translate}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    passed = total = skipped = 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                results = fn(tmp)
            except Exception as e:
                results = {f"{name} ran without crashing": False}
                print(f"  {name}: {type(e).__name__}: {e}")
        for check, ok in results.items():
            if ok is SKIP:
                skipped += 1
                print(f"  SKIP  {name}: {check}")
                continue
            total += 1
            passed += bool(ok)
            print(f"  {'PASS' if ok else 'FAIL'}  {name}: {check}")
    print(f"\n{passed}/{total}" + (f", {skipped} skipped (not proven on this machine)" if skipped else ""))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
