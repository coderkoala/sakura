#!/usr/bin/env python3
"""conv's later formats — books, sheets, office files, OCR, denoise, stems — graded by what is in the files it writes, never
by what it prints. An epub is unzipped and its OPF and chapters read; a Kindle file is converted back and read again; a
denoised recording is decoded and its hiss measured between the notes; a scan's words are looked for with pdftotext; a
spreadsheet's cells are read back out of the csv. Fixtures are generated here (ffmpeg, Pillow, openpyxl, pandoc).

  evals/formats.py              every case
  evals/formats.py --only NAME  one of: books kindle denoise stems ocr office
A check whose tool isn't on this machine is SKIPPED and says why (it isn't a pass). No model, no network.
  SAKURA_EVAL_RNNN=FILE.rnnn    also proves `conv denoise --model` with that rnnoise model
"""

import argparse
import csv
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
CONV = os.path.join(BIN, "conv")
SKIP = object()
FF = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]

BOOK = """---
title: The Juniper Road
author: Maya Gurung
---

# Chapter One

The marmot crossed the ridge at dawn.

# Chapter Two

Snow fell on Thorong La before the porters woke.
"""
LINE1, LINE2 = (
    "The marmot crossed the ridge at dawn.",
    "Snow fell on Thorong La before the porters woke.",
)


def run(args, env=None, cwd=None, timeout=300):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(
        args, env=e, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def only(tmp, name, *tools):
    """A PATH holding nothing but these tools, so conv can be watched without the others."""
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    for t in tools:
        p = shutil.which(t)
        if p:
            os.symlink(p, os.path.join(d, t))
    return d


def conv(tmp, *args, path=None, env=None):
    e = dict(env or {})
    if path is not None:
        e["PATH"] = path
    return run([sys.executable, CONV, *args], e, cwd=tmp)


def raw(path):
    return open(path, "rb").read()


def epub_parts(path):
    """(the OPF, every chapter's text) out of the zip an epub is."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            opf = "".join(
                z.read(n).decode("utf-8", "replace")
                for n in names
                if n.endswith(".opf")
            )
            body = "".join(
                z.read(n).decode("utf-8", "replace")
                for n in names
                if n.endswith((".xhtml", ".html", ".htm"))
            )
            first = (
                names[0] == "mimetype"
                and z.read("mimetype").strip() == b"application/epub+zip"
            )
        return opf, body, first
    except (OSError, zipfile.BadZipFile, KeyError, IndexError):
        return "", "", False


def docx_text(path):
    try:
        with zipfile.ZipFile(path) as z:
            import re

            return re.sub(
                r"<[^>]+>",
                "",
                z.read("word/document.xml")
                .decode("utf-8", "replace")
                .replace("</w:p>", "\n"),
            )
    except (OSError, zipfile.BadZipFile, KeyError):
        return ""


def pdf_text(path):
    return (
        run(["pdftotext", "-layout", path, "-"]).stdout if os.path.exists(path) else ""
    )


def text(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def books(tmp):
    if not shutil.which("pandoc"):
        return {"books (pandoc not installed)": SKIP}
    open(os.path.join(tmp, "book.md"), "w").write(BOOK)
    open(os.path.join(tmp, "plain notes.md"), "w").write(
        "# One\n\nNo front matter here.\n"
    )
    before = raw(os.path.join(tmp, "book.md"))
    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    out = {}

    conv(tmp, "book.md", "--to", "epub")
    opf, body, first = epub_parts(p("book.epub"))
    out[
        "md → epub is a real epub: the mimetype entry first, the chapters' text inside"
    ] = first and LINE1 in body and LINE2 in body
    out["the epub's OPF carries the title and the author from the front matter"] = (
        "The Juniper Road</dc:title>" in opf and "Maya Gurung</dc:creator>" in opf
    )
    first_bytes = raw(p("book.epub")) if os.path.exists(p("book.epub")) else b""

    conv(tmp, "book.md", "--to", "epub")
    out["a second run writes book (2).epub and leaves the first alone"] = (
        os.path.exists(p("book (2).epub"))
        and raw(p("book.epub")) == first_bytes
        and bool(first_bytes)
    )

    conv(tmp, "book.epub", "--to", "md", "-o", "back.md")
    back = text(p("back.md"))
    out[
        "epub → md keeps both chapters, their headings, and the title and author as front matter"
    ] = (
        LINE1 in back
        and LINE2 in back
        and "# Chapter One" in back
        and "title: The Juniper Road" in back
        and "author: Maya Gurung" in back
    )
    conv(tmp, "back.md", "--to", "epub", "-o", "again.epub")
    opf2, body2, _ = epub_parts(p("again.epub"))
    out["md → epub → md → epub: the text, title and author survive the round trip"] = (
        LINE1 in body2
        and LINE2 in body2
        and "The Juniper Road</dc:title>" in opf2
        and "Maya Gurung</dc:creator>" in opf2
    )

    conv(tmp, "book.epub", "--to", "docx")
    conv(tmp, "book.epub", "--to", "txt")
    conv(tmp, "book.epub", "--to", "html")
    out["epub → docx, txt and html each hold the chapter text"] = all(
        LINE2 in t
        for t in (docx_text(p("book.docx")), text(p("book.txt")), text(p("book.html")))
    )
    out["epub → html keeps the book's title, not the file's name"] = (
        "<title>The Juniper Road</title>" in text(p("book.html"))
    )

    conv(tmp, "book.epub", "--to", "fb2")
    fb2 = text(p("book.fb2"))
    conv(tmp, "book.fb2", "--to", "epub", "-o", "fromfb2.epub")
    out[
        "epub → fb2 → epub: FictionBook with the title, and the text back in an epub"
    ] = (
        "<book-title>The Juniper Road</book-title>" in fb2
        and LINE1 in fb2
        and LINE1 in epub_parts(p("fromfb2.epub"))[1]
    )

    conv(
        tmp,
        "book.md",
        "--to",
        "epub",
        "--title",
        "Another Name",
        "--author",
        "Tsering Lama",
        "-o",
        "named.epub",
    )
    opf3 = epub_parts(p("named.epub"))[0]
    out["--title and --author replace the front matter's in the OPF"] = (
        "Another Name</dc:title>" in opf3
        and "Tsering Lama</dc:creator>" in opf3
        and "Juniper" not in opf3
    )

    conv(tmp, "plain notes.md", "--to", "epub")
    out["a markdown file with no front matter gets its file name as the title"] = (
        "plain notes</dc:title>" in epub_parts(p("plain notes.epub"))[0]
    )

    conv(tmp, "book.md", "--to", "docx", "-o", "manuscript.docx")
    conv(tmp, "manuscript.docx", "--to", "epub")
    out["docx → epub holds the text and the title"] = (
        LINE1 in epub_parts(p("manuscript.epub"))[1]
        and "The Juniper Road</dc:title>" in epub_parts(p("manuscript.epub"))[0]
    )

    # pandoc alone, calibre hidden: the pairs pandoc can do still work, the Kindle ones say what to install and write nothing
    alone = only(tmp, "pandoc-only", "pandoc")
    conv(tmp, "book.epub", "--to", "md", "-o", "alone.md", path=alone)
    out["with only pandoc on PATH, epub → md still works"] = LINE1 in text(
        p("alone.md")
    )
    listing = sorted(os.listdir(tmp))
    r = conv(tmp, "book.epub", "--to", "mobi", path=alone)
    r2 = conv(tmp, "book.md", "--to", "azw3", path=alone)
    out[
        "with no calibre, → mobi and → azw3 exit non-zero, name `apt-get install -y calibre`, and write nothing"
    ] = (
        r.returncode != 0
        and r2.returncode != 0
        and "apt-get install -y calibre" in r.stderr
        and "apt-get install -y calibre" in r2.stderr
        and sorted(os.listdir(tmp)) == listing
    )
    nothing = only(tmp, "nothing")
    r = conv(tmp, "book.epub", "--to", "md", "-o", "none.md", path=nothing)
    out["with neither, epub → md names pandoc's install line and writes nothing"] = (
        r.returncode != 0
        and "apt-get install -y pandoc" in r.stderr
        and not os.path.exists(p("none.md"))
    )

    r = conv(tmp, "book.md", "--to", "epub", "-o", "dry.epub", "--dry")
    out["--dry prints the pandoc command and writes nothing"] = (
        "pandoc" in r.stdout and not os.path.exists(p("dry.epub"))
    )
    out["the markdown it started from is byte-for-byte unchanged"] = (
        raw(p("book.md")) == before
    )
    return out


def kindle(tmp):
    if not shutil.which("ebook-convert"):
        return {
            "mobi and azw3 (calibre's ebook-convert not installed: sudo apt-get install -y calibre)": SKIP
        }
    if not shutil.which("pandoc"):
        return {"mobi and azw3 (pandoc not installed)": SKIP}
    from pypdf import PdfReader

    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    open(p("book.md"), "w").write(BOOK)
    out = {}
    conv(tmp, "book.md", "--to", "mobi")
    conv(tmp, "book.md", "--to", "azw3")
    conv(tmp, "book.md", "--to", "epub")
    blobs = {
        f: (raw(p(f)) if os.path.exists(p(f)) else b"")
        for f in ("book.md", "book.mobi", "book.azw3", "book.epub")
    }
    out[
        "md → mobi and → azw3 are Kindle files (BOOKMOBI at byte 60) with the title in the header"
    ] = all(
        blobs[f][60:68] == b"BOOKMOBI" and b"The Juniper Road" in blobs[f]
        for f in ("book.mobi", "book.azw3")
    )

    conv(tmp, "book.mobi", "--to", "epub", "-o", "frommobi.epub")
    opf, body, first = epub_parts(p("frommobi.epub"))
    out["mobi → epub: both chapters' text, and the title and author in the OPF"] = (
        first
        and LINE1 in body
        and LINE2 in body
        and "The Juniper Road</dc:title>" in opf
        and "Maya Gurung</dc:creator>" in opf
    )

    conv(tmp, "book.azw3", "--to", "epub", "-o", "fromazw3.epub")
    opf, body, _ = epub_parts(p("fromazw3.epub"))
    out["azw3 → epub: the same"] = (
        LINE1 in body
        and LINE2 in body
        and "The Juniper Road</dc:title>" in opf
        and "Maya Gurung</dc:creator>" in opf
    )

    conv(tmp, "book.epub", "--to", "azw3", "-o", "e.azw3")
    conv(tmp, "e.azw3", "--to", "mobi", "-o", "e.mobi")
    conv(tmp, "e.mobi", "--to", "txt", "-o", "e.txt")
    out["epub → azw3 → mobi → txt: the text survives three readers' formats"] = (
        LINE1 in text(p("e.txt")) and LINE2 in text(p("e.txt"))
    )

    conv(tmp, "book.azw3", "--to", "md", "-o", "k.md")
    k = text(p("k.md"))
    out[
        "azw3 → md (calibre opens it, pandoc writes it): text, and the title as front matter"
    ] = LINE1 in k and LINE2 in k and "title: The Juniper Road" in k

    conv(tmp, "book.mobi", "--to", "docx", "-o", "k.docx")
    out["mobi → docx holds the text"] = LINE2 in docx_text(p("k.docx"))

    conv(tmp, "book.epub", "--to", "pdf", "-o", "k.pdf")
    title = ""
    try:
        title = (PdfReader(p("k.pdf")).metadata or {}).get("/Title", "")
    except Exception:
        pass
    flat = " ".join(pdf_text(p("k.pdf")).split())
    out[
        "epub → pdf (calibre): the text is in the pages and the title in the pdf's metadata"
    ] = LINE1 in flat and LINE2 in flat and title == "The Juniper Road"

    conv(
        tmp,
        "book.mobi",
        "--to",
        "epub",
        "--title",
        "Renamed",
        "--author",
        "Pasang Sherpa",
        "-o",
        "r.epub",
    )
    opf = epub_parts(p("r.epub"))[0]
    out["--title and --author reach calibre too"] = (
        "Renamed</dc:title>" in opf and "Pasang Sherpa</dc:creator>" in opf
    )

    listing = sorted(os.listdir(tmp))
    r = conv(tmp, "book.epub", "--to", "azw")
    out["--to azw is refused with the format to ask for, nothing written"] = (
        r.returncode != 0 and "azw3" in r.stderr and sorted(os.listdir(tmp)) == listing
    )
    out["no input was changed"] = all(raw(p(f)) == b for f, b in blobs.items()) and all(
        blobs.values()
    )
    return out


# ---- sound


def pcm(path, rate=44100):
    import numpy as np

    data = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            path,
            "-vn",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(rate),
            "-",
        ],
        capture_output=True,
    ).stdout
    return np.frombuffer(data, dtype=np.int16).astype(float) / 32768


def levels(path, rate=44100):
    """(hiss between the notes, the notes themselves, seconds): mean power in dB over the planted gaps and bursts, after 2 s."""
    import numpy as np

    x = pcm(path, rate)
    if len(x) < rate * 3:
        return 0.0, 0.0, len(x) / rate
    t = np.arange(len(x)) / rate
    phase = np.mod(t, 1.0)
    late = t > 2.0
    gap = x[late & (phase > 0.6) & (phase < 0.9)]
    note = x[late & (phase > 0.1) & (phase < 0.4)]
    db = lambda v: 10 * np.log10(np.mean(v**2) + 1e-12)  # noqa: E731
    return db(gap), db(note), len(x) / rate


def noisy(path, video=False, seconds=6):
    """A 440 Hz note for the first half of every second, white hiss all the way through."""
    src = [
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={seconds}:sample_rate=44100",
        "-f",
        "lavfi",
        "-i",
        f"anoisesrc=color=white:amplitude=0.03:duration={seconds}:sample_rate=44100:seed=7",
    ]
    mix = "[{0}:a]volume='if(lt(mod(t,1),0.5),2,0)':eval=frame[n];[n][{1}:a]amix=inputs=2:normalize=0[a]"
    if video:
        subprocess.run(
            [
                *FF,
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={seconds}:size=160x120:rate=10",
                *src,
                "-filter_complex",
                mix.format(1, 2),
                "-map",
                "0:v",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                path,
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                *FF,
                *src,
                "-filter_complex",
                mix.format(0, 1),
                "-map",
                "[a]",
                "-c:a",
                "pcm_s16le",
                path,
            ],
            check=True,
        )


def video_md5(path):
    r = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            path,
            "-map",
            "0:v",
            "-c",
            "copy",
            "-f",
            "md5",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def denoise(tmp):
    if not shutil.which("ffmpeg"):
        return {"denoise (ffmpeg not installed)": SKIP}
    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    noisy(p("tape.wav"))
    noisy(p("film.mp4"), video=True)
    before = {f: raw(p(f)) for f in ("tape.wav", "film.mp4")}
    hiss0, note0, dur0 = levels(p("tape.wav"))
    out = {}

    conv(tmp, "denoise", "tape.wav")
    hiss1, note1, dur1 = (
        levels(p("tape denoised.wav"))
        if os.path.exists(p("tape denoised.wav"))
        else (0, 0, 0)
    )
    out[
        "the hiss between the notes drops by 8 dB or more (measured from the samples), default settings"
    ] = hiss1 < hiss0 - 8
    out["the note itself keeps its level within 1.5 dB, and the length is the same"] = (
        abs(note1 - note0) < 1.5 and abs(dur1 - dur0) < 0.05
    )

    conv(tmp, "denoise", "tape.wav", "--strength", "3", "-o", "light.wav")
    conv(tmp, "denoise", "tape.wav", "--strength", "30", "-o", "heavy.wav")
    light, heavy = levels(p("light.wav"))[0], levels(p("heavy.wav"))[0]
    out[
        "--strength is a real knob: 3 takes off a little, 30 at least 10 dB more than that"
    ] = hiss0 - 6 < light < hiss0 - 1 and heavy < light - 10

    conv(
        tmp,
        "denoise",
        "tape.wav",
        "--floor",
        "-80",
        "--strength",
        "30",
        "-o",
        "wrongfloor.wav",
    )
    out[
        "--floor is passed through: told the floor is -80 dB, it leaves this (louder) hiss nearly alone"
    ] = (
        os.path.exists(p("wrongfloor.wav"))
        and levels(p("wrongfloor.wav"))[0] > hiss0 - 3
    )

    conv(tmp, "denoise", "film.mp4")
    made = p("film denoised.mp4")
    vh0, vn0, vd0 = levels(p("film.mp4"))
    vh1, vn1, vd1 = levels(made) if os.path.exists(made) else (0, 0, 0)
    out["a video: its hiss drops 8 dB, the note stays, the length stays"] = (
        vh1 < vh0 - 8 and abs(vn1 - vn0) < 1.5 and abs(vd1 - vd0) < 0.1
    )
    out[
        "a video: the picture stream is copied, packet for packet (same md5), not re-encoded"
    ] = video_md5(made) is not None and video_md5(made) == video_md5(p("film.mp4"))

    listing = sorted(os.listdir(tmp))
    bad = [
        conv(tmp, "denoise", "tape.wav", "--strength", "400", "-o", "x1.wav"),
        conv(tmp, "denoise", "tape.wav", "--floor", "-5", "-o", "x2.wav"),
        conv(tmp, "denoise", "tape.wav", "--model", "nope.rnnn", "-o", "x3.wav"),
        conv(tmp, "denoise", "missing.wav"),
    ]
    open(p("letter.pdf"), "wb").write(b"%PDF-1.4\n")
    bad.append(conv(tmp, "denoise", "letter.pdf"))
    os.unlink(p("letter.pdf"))
    out[
        "a strength or floor out of afftdn's range, a missing model, a missing file, a pdf: each refused, nothing written"
    ] = all(r.returncode != 0 for r in bad) and sorted(os.listdir(tmp)) == listing

    r = conv(tmp, "denoise", "tape.wav", "-o", "dry.wav", "--dry")
    out["--dry prints the ffmpeg command and writes nothing"] = (
        "afftdn" in r.stdout and not os.path.exists(p("dry.wav"))
    )

    rnnn = os.environ.get("SAKURA_EVAL_RNNN")
    if rnnn and os.path.isfile(rnnn):
        conv(tmp, "denoise", "tape.wav", "--model", rnnn, "-o", "net.wav")
        nh, _, nd = (
            levels(p("net.wav"), 48000) if os.path.exists(p("net.wav")) else (0, 0, 0)
        )
        out[
            "--model FILE.rnnn (arnndn): the hiss drops 8 dB and the length is the same"
        ] = nh < levels(p("tape.wav"), 48000)[0] - 8 and abs(nd - dur0) < 0.05
        r = conv(
            tmp,
            "denoise",
            "tape.wav",
            "--model",
            rnnn,
            "--strength",
            "20",
            "-o",
            "x4.wav",
        )
        out["--model with --strength is refused: the network has no such knob"] = (
            r.returncode != 0 and not os.path.exists(p("x4.wav"))
        )
    else:
        out[
            "--model FILE.rnnn through arnndn (no model is shipped; SAKURA_EVAL_RNNN=FILE proves it)"
        ] = SKIP
    out["the recordings it started from are byte-for-byte unchanged"] = all(
        raw(p(f)) == b for f, b in before.items()
    )
    return out


FAKE_DEMUCS = r"""#!/usr/bin/env python3
# stands in for demucs: writes the files demucs would, where demucs would, and records how it was called
import json, os, shutil, sys
a = sys.argv[1:]
json.dump(a, open(os.environ["FAKE_DEMUCS_LOG"], "a")); open(os.environ["FAKE_DEMUCS_LOG"], "a").write("\n")
if os.environ.get("FAKE_DEMUCS_FAIL"):
    out = a[a.index("-o") + 1]
    os.makedirs(os.path.join(out, "htdemucs", "half"), exist_ok=True)
    open(os.path.join(out, "htdemucs", "half", "junk.tmp"), "w").write("x")
    sys.stderr.write("CUDA out of memory\n"); sys.exit(1)
out = a[a.index("-o") + 1]
model = a[a.index("-n") + 1] if "-n" in a else "htdemucs"
track = a[-1]
names = ["vocals", "no_vocals"] if "--two-stems" in a else ["vocals", "drums", "bass", "other"]
d = os.path.join(out, model, os.path.splitext(os.path.basename(track))[0])
os.makedirs(d)
for n in names:
    shutil.copy(track, os.path.join(d, n + ".wav"))
    open(os.path.join(d, n + ".wav"), "ab").write(n.encode())
"""


def stems(tmp):
    if not shutil.which("ffmpeg"):
        return {"stems (ffmpeg not installed, to make the song)": SKIP}
    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    work = os.path.join(tmp, "music")
    os.makedirs(work)
    w = lambda f: os.path.join(work, f)  # noqa: E731
    subprocess.run(
        [*FF, "-f", "lavfi", "-i", "sine=frequency=330:duration=2", w("song.wav")],
        check=True,
    )
    before = raw(w("song.wav"))
    fake = only(tmp, "fake-bin")
    open(os.path.join(fake, "demucs"), "w").write(FAKE_DEMUCS)
    os.chmod(os.path.join(fake, "demucs"), 0o755)
    log = p("calls.jsonl")
    env = {"FAKE_DEMUCS_LOG": log}
    path = (
        fake
        + os.pathsep
        + os.path.dirname(sys.executable)
        + os.pathsep
        + "/usr/bin:/bin"
    )
    calls = lambda: (
        [__import__("json").loads(line) for line in open(log)]
        if os.path.exists(log)
        else []
    )  # noqa: E731
    out = {}

    r = conv(work, "stems", "song.wav", path=path, env=env)
    d = w("song stems")
    got = sorted(os.listdir(d)) if os.path.isdir(d) else []
    out["four stems land flat in a new “song stems” folder next to the song"] = (
        r.returncode == 0
        and got == ["bass.wav", "drums.wav", "other.wav", "vocals.wav"]
    )
    out["each file is the one demucs wrote under that name"] = bool(got) and all(
        raw(os.path.join(d, f)).endswith(f[:-4].encode()) for f in got
    )
    out[
        "demucs was handed the song, and nothing of its own layout or conv's work folder is left behind"
    ] = (
        bool(calls())
        and calls()[0][-1] == "song.wav"
        and sorted(os.listdir(work)) == ["song stems", "song.wav"]
    )

    conv(
        work,
        "stems",
        "song.wav",
        "--two",
        "vocals",
        "--model",
        "htdemucs_ft",
        path=path,
        env=env,
    )
    d2 = w("song stems (2)")
    last = calls()[-1] if calls() else []
    out[
        "--two vocals and --model reach demucs as --two-stems vocals and -n, and a second run gets its own folder"
    ] = (
        os.path.isdir(d2)
        and sorted(os.listdir(d2)) == ["no_vocals.wav", "vocals.wav"]
        and "--two-stems vocals" in " ".join(last)
        and "-n htdemucs_ft" in " ".join(last)
        and sorted(os.listdir(d)) == got
    )

    listing = sorted(os.listdir(work))
    r = conv(work, "stems", "song.wav", path=path, env=dict(env, FAKE_DEMUCS_FAIL="1"))
    out[
        "when demucs fails, conv exits non-zero, shows why, and leaves no folder or half-made files"
    ] = (
        r.returncode != 0
        and "CUDA out of memory" in r.stderr
        and sorted(os.listdir(work)) == listing
    )

    r = conv(work, "stems", "song.wav", "-o", "song stems", path=path, env=env)
    out["-o onto a folder that exists is refused, and what's in it is untouched"] = (
        r.returncode != 0
        and sorted(os.listdir(d)) == got
        and sorted(os.listdir(work)) == listing
    )

    n_calls = len(calls())
    bare = only(tmp, "no-demucs", "ffmpeg")
    r = conv(work, "stems", "song.wav", path=bare, env=env)
    out[
        "with no demucs: non-zero exit, the install command named, nothing written anywhere"
    ] = (
        r.returncode != 0
        and "uv tool install demucs" in r.stderr
        and sorted(os.listdir(work)) == listing
        and len(calls()) == n_calls
    )
    r = conv(work, "stems", "song.wav", "--dry", path=path, env=env)
    out["--dry prints the demucs command, runs nothing, writes nothing"] = (
        "demucs" in r.stdout
        and len(calls()) == n_calls
        and sorted(os.listdir(work)) == listing
    )
    out["the song is byte-for-byte unchanged"] = raw(w("song.wav")) == before

    real = shutil.which("demucs")
    cached = glob.glob(os.path.expanduser("~/.cache/torch/hub/checkpoints/*.th"))
    if not real:
        out[
            "a real separation (demucs not installed: uv tool install demucs --with numpy)"
        ] = SKIP
    elif not cached and not os.environ.get("SAKURA_EVAL_NETWORK"):
        out[
            "a real separation (demucs is here but its model isn't; SAKURA_EVAL_NETWORK=1 lets it fetch it)"
        ] = SKIP
    else:
        import numpy as np

        realdir = os.path.join(tmp, "real")
        os.makedirs(realdir)
        # a low bass note under noise bursts that stand in for a snare: demucs should put most of the note in bass
        subprocess.run(
            [
                *FF,
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=70:duration=6:sample_rate=44100",
                "-f",
                "lavfi",
                "-i",
                "anoisesrc=color=white:amplitude=0.4:duration=6:sample_rate=44100:seed=3",
                "-filter_complex",
                "[0:a]volume=4[b];[1:a]volume='if(lt(mod(t,0.5),0.05),1,0)':eval=frame[d];[b][d]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo[a]",
                "-map",
                "[a]",
                os.path.join(realdir, "mix.wav"),
            ],
            check=True,
        )
        r = run([sys.executable, CONV, "stems", "mix.wav"], cwd=realdir, timeout=1800)
        sd = os.path.join(realdir, "mix stems")
        names = sorted(os.listdir(sd)) if os.path.isdir(sd) else []
        ok = r.returncode == 0 and names == [
            "bass.wav",
            "drums.wav",
            "other.wav",
            "vocals.wav",
        ]
        if ok:
            mix = pcm(os.path.join(realdir, "mix.wav"))
            parts = {n: pcm(os.path.join(sd, n)) for n in names}
            total = sum(parts.values())
            m = min(len(mix), len(total))
            low = lambda x: float(
                np.sum(np.abs(np.fft.rfft(x))[: int(120 * len(x) / 44100)] ** 2)
            )  # noqa: E731
            ok = (
                abs(len(mix) - len(total)) < 4410
                and np.corrcoef(mix[:m], total[:m])[0, 1] > 0.9
                and low(parts["bass.wav"]) > 3 * low(parts["drums.wav"])
            )
        out[
            "a real separation: four stems as long as the song, adding back up to it, the 70 Hz note mostly in bass"
        ] = ok
    return out


# ---- scans and office files


def scan_image(words, size=(1700, 700)):
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    font = None
    for f in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 72)
            break
    font = font or ImageFont.load_default(size=72)
    for i, line in enumerate(words):
        d.text((100, 120 + i * 160), line, fill="black", font=font)
    return im


def ocr(tmp):
    if not shutil.which("tesseract"):
        return {
            "ocr (tesseract not installed: sudo apt-get install -y tesseract-ocr)": SKIP
        }
    if not shutil.which("pdftotext"):
        return {
            "ocr (pdftotext not installed, to read the result: sudo apt-get install -y poppler-utils)": SKIP
        }
    from pypdf import PdfReader

    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    one = scan_image(["INVOICE 4471", "Kathmandu Paper Works"])
    two = scan_image(["RECEIPT 9082", "Pokhara Lakeside"])
    one.save(
        p("scan.pdf"), save_all=True, append_images=[two], resolution=200
    )  # two pages, pictures only
    one.save(p("photo.png"), dpi=(200, 200))
    before = {f: raw(p(f)) for f in ("scan.pdf", "photo.png")}
    blank = "4471" not in pdf_text(p("scan.pdf")) and "Kathmandu" not in pdf_text(
        p("scan.pdf")
    )
    out = {}

    def page(path, n):
        return (
            run(["pdftotext", "-f", str(n), "-l", str(n), path, "-"]).stdout
            if os.path.exists(path)
            else ""
        )

    if shutil.which("ocrmypdf"):
        conv(tmp, "ocr", "scan.pdf")
        made = p("scan ocr.pdf")
        out[
            "an image-only pdf (pdftotext finds nothing in it) comes back searchable: pdftotext finds the words"
        ] = blank and "4471" in page(made, 1) and "Kathmandu" in page(made, 1)
        out["each page's words are on that page, and there are still two pages"] = (
            "9082" in page(made, 2)
            and "Pokhara" in page(made, 2)
            and "9082" not in page(made, 1)
            and os.path.exists(made)
            and len(PdfReader(made).pages) == 2
        )
        conv(tmp, "ocr", "photo.png", "-o", "photo.pdf")
        out["an image becomes a searchable pdf (ocrmypdf)"] = "INVOICE" in pdf_text(
            p("photo.pdf")
        ) and "4471" in pdf_text(p("photo.pdf"))
        conv(tmp, "ocr", "scan ocr.pdf", "-o", "twice.pdf")
        out[
            "a pdf that already has its text isn't given a second layer (each word still once)"
        ] = pdf_text(p("twice.pdf")).count("4471") == 1
    else:
        out[
            "a scanned pdf becomes searchable (ocrmypdf not installed: uv tool install ocrmypdf)"
        ] = SKIP

    alone = only(tmp, "tesseract-only", "tesseract")
    conv(tmp, "ocr", "photo.png", "-o", "t.pdf", path=alone)
    out["with tesseract alone on PATH, an image still becomes a searchable pdf"] = (
        "4471" in pdf_text(p("t.pdf")) and "Kathmandu" in pdf_text(p("t.pdf"))
    )
    listing = sorted(os.listdir(tmp))
    r = conv(tmp, "ocr", "scan.pdf", "-o", "t2.pdf", path=alone)
    out[
        "with tesseract alone, a pdf is refused with ocrmypdf's install line, nothing written"
    ] = (
        r.returncode != 0
        and "ocrmypdf" in r.stderr
        and sorted(os.listdir(tmp)) == listing
    )
    r = conv(tmp, "ocr", "photo.png", "-o", "t3.pdf", path=only(tmp, "none"))
    out["with neither, it names tesseract's install line and writes nothing"] = (
        r.returncode != 0
        and "apt-get install -y tesseract-ocr" in r.stderr
        and not os.path.exists(p("t3.pdf"))
    )
    out["the scans are byte-for-byte unchanged"] = all(
        raw(p(f)) == b for f, b in before.items()
    )
    return out


def office(tmp):
    if not (shutil.which("libreoffice") or shutil.which("soffice")):
        return {
            "office files (LibreOffice not installed: sudo apt-get install -y libreoffice-core libreoffice-writer libreoffice-calc)": SKIP
        }
    import openpyxl
    from docx import Document

    p = lambda f: os.path.join(tmp, f)  # noqa: E731
    sentence = "The quarterly yak census counted 318 animals."
    doc = Document()
    doc.add_heading("Census Report", 1)
    doc.add_paragraph(sentence)
    doc.save(p("report.docx"))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Herds"
    rows = [
        ["village", "yaks", "note"],
        ["Manang", 120, "high pasture, north"],
        ["Mustang", 198, "नेपाल"],
    ]
    for r in rows:
        ws.append(r)
    ws.append(["total", "=SUM(B2:B3)", ""])
    wb.save(p("one.xlsx"))
    ws2 = wb.create_sheet("Prices")
    ws2.append(["item", "rupees"])
    ws2.append(["salt", 45.5])
    wb.save(p("two.xlsx"))
    open(p("list.csv"), "w", newline="").write("name,qty\nrope,7\ntent,2\n")
    inputs = ("report.docx", "one.xlsx", "two.xlsx", "list.csv")
    before = {f: raw(p(f)) for f in inputs}
    out = {}

    def table(path):
        try:
            return list(csv.reader(open(path, encoding="utf-8", newline="")))
        except OSError:
            return []

    conv(tmp, "report.docx", "--to", "pdf")
    flat = " ".join(pdf_text(p("report.pdf")).split())
    out["docx → pdf: the heading and the sentence are in the pdf's text"] = (
        sentence in flat and "Census Report" in flat
    )
    first = raw(p("report.pdf")) if os.path.exists(p("report.pdf")) else b""
    conv(tmp, "report.docx", "--to", "pdf")
    out["a second docx → pdf writes report (2).pdf and leaves the first alone"] = (
        os.path.exists(p("report (2).pdf"))
        and bool(first)
        and raw(p("report.pdf")) == first
    )

    conv(tmp, "report.docx", "--to", "odt")
    conv(tmp, "report.odt", "--to", "docx", "-o", "back.docx")
    odt = ""
    try:
        odt = (
            zipfile.ZipFile(p("report.odt"))
            .read("content.xml")
            .decode("utf-8", "replace")
        )
    except (OSError, zipfile.BadZipFile, KeyError):
        pass
    out[
        "docx → odt → docx: the sentence is in the odt's content.xml and in the docx that comes back"
    ] = sentence in odt and sentence in docx_text(p("back.docx"))

    conv(tmp, "one.xlsx", "--to", "csv")
    t = table(p("one.csv"))
    out[
        "xlsx → csv: the cells row for row, a comma kept inside its cell, Devanagari intact (UTF-8)"
    ] = t[:3] == [
        ["village", "yaks", "note"],
        ["Manang", "120", "high pasture, north"],
        ["Mustang", "198", "नेपाल"],
    ]
    out["xlsx → csv: a formula comes out as its value (=SUM → 318)"] = len(t) > 3 and t[
        3
    ][:2] == ["total", "318"]

    conv(tmp, "two.xlsx", "--to", "csv")
    out[
        "a workbook with two sheets gives one csv per sheet, named for the sheet, each with its own rows"
    ] = (
        table(p("two Herds.csv"))[1:2] == [["Manang", "120", "high pasture, north"]]
        and table(p("two Prices.csv")) == [["item", "rupees"], ["salt", "45.5"]]
        and not os.path.exists(p("two.csv"))
    )

    conv(tmp, "one.xlsx", "--to", "pdf")
    flat = " ".join(pdf_text(p("one.pdf")).split())
    out["xlsx → pdf: the cells' text and the computed total are in the pdf"] = (
        "Manang" in flat and "high pasture, north" in flat and "318" in flat
    )

    conv(tmp, "list.csv", "--to", "xlsx")
    back = []
    try:
        back = [
            list(r)
            for r in openpyxl.load_workbook(p("list.xlsx")).active.iter_rows(
                values_only=True
            )
        ]
    except Exception:
        pass
    out["csv → xlsx: the rows read back with openpyxl, numbers as numbers"] = back == [
        ["name", "qty"],
        ["rope", 7],
        ["tent", 2],
    ]

    conv(tmp, "one.xlsx", "--to", "ods")
    conv(tmp, "one.ods", "--to", "csv", "-o", "fromods.csv")
    out["xlsx → ods → csv: the same cells come back"] = table(p("fromods.csv"))[
        :3
    ] == t[:3] and bool(t)

    if shutil.which("pandoc"):
        open(p("deck.md"), "w").write(
            "# Trek plan\n\n- Leave Besisahar on Monday\n\n# Kit\n\n- Crampons for the pass\n"
        )
        subprocess.run(["pandoc", p("deck.md"), "-o", p("deck.pptx")], check=True)
        conv(tmp, "deck.pptx", "--to", "pdf")
        flat = " ".join(pdf_text(p("deck.pdf")).split())
        out["pptx → pdf: both slides' text is in the pdf"] = (
            "Leave Besisahar on Monday" in flat and "Crampons for the pass" in flat
        )
    else:
        out["pptx → pdf (pandoc not installed, to make the deck)"] = SKIP
    out["the office files it started from are byte-for-byte unchanged"] = all(
        raw(p(f)) == b for f, b in before.items()
    )
    return out


def edges(tmp):
    """Two things that used to go wrong at the edges: slides from markdown, and a file that isn't the PDF its name says."""
    import zipfile
    conv = os.path.join(BIN, "conv")
    deck = os.path.join(tmp, "deck.md")
    open(deck, "w").write("# First\n\n- one\n- two\n\n# Second\n\nwords\n")
    r = subprocess.run([conv, deck, "--to", "pptx"], capture_output=True, text=True, cwd=tmp)
    out = os.path.join(tmp, "deck.pptx")
    slides, text = 0, ""
    if os.path.exists(out):
        z = zipfile.ZipFile(out)
        names = [n for n in z.namelist() if n.startswith("ppt/slides/slide")]
        slides, text = len(names), "".join(z.read(n).decode("utf-8", "replace") for n in names)
    fake = os.path.join(tmp, "form.pdf")
    open(fake, "w").write("not a pdf\n")
    f = subprocess.run([conv, "fields", fake], capture_output=True, text=True, cwd=tmp)
    g = subprocess.run([conv, "pages", fake], capture_output=True, text=True, cwd=tmp)
    return {
        "markdown becomes slides, one per heading, with its words": r.returncode == 0 and slides == 2 and "First" in text and "two" in text,
        "a file that isn't a PDF is one plain line and exit 1, not a traceback": f.returncode == 1 and "isn't a PDF" in f.stderr and "Traceback" not in f.stderr + g.stderr and g.returncode != 0,
    }


CASES = {
    "books": books,
    "kindle": kindle,
    "denoise": denoise,
    "stems": stems,
    "ocr": ocr,
    "office": office,
    "edges": edges,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    total = passed = skipped = 0
    for name, fn in CASES.items():
        if a.only and a.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                results = fn(tmp)
            except Exception as e:  # a crash is a failure with a reason, not a stack trace in the summary
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
    print(
        f"\n{passed}/{total}"
        + (f", {skipped} skipped (not proven on this machine)" if skipped else "")
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
