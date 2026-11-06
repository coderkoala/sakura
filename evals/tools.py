#!/usr/bin/env python3
"""Do the file, document and office tools work when the model drives them? Graded by what's on disk, never by what it says.

  evals/tools.py                 every case
  evals/tools.py --only NAME
Reports which commands it used, so adoption of the tools can be seen.
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

MODULE = "".join(f"def helper_{i}(x):\n    return x + {i}\n\n" for i in range(40)) + "def total(items):\n    result = 1\n    for item in items:\n        result += item\n    return result\n\n" + "".join(f"def after_{i}(x):\n    return x - {i}\n\n" for i in range(40))


def zip_text(path, member_prefix):
    with zipfile.ZipFile(path) as z:
        return " ".join("".join(ET.fromstring(z.read(n)).itertext()) for n in z.namelist() if n.startswith(member_prefix) and n.endswith(".xml"))


def edit_a_function(d):
    open("calc.py", "w").write(MODULE)
    return "total() in calc.py is wrong: it should sum the items, but it starts from 1. Fix that one line and change nothing else.", lambda final: {
        "the bug is fixed": subprocess.run(["python3", "-c", "import calc; assert calc.total([1,2]) == 3"], capture_output=True).returncode == 0,
        "only one line changed": sum(a != b for a, b in zip(MODULE.splitlines(), open("calc.py").read().splitlines())) == 1 and len(open("calc.py").read().splitlines()) == len(MODULE.splitlines())}


def find_in_big_file(d):
    with open("big.log", "w") as f:
        for i in range(30000):
            f.write(f"2026-11-05 line {i} ok\n" if i != 21234 else "2026-11-05 line 21234 FATAL disk quota exceeded on volume TEAL-9\n")
    return "big.log has one FATAL line. Which volume does it name?", lambda final: {"found the volume": "TEAL-9" in final}


def new_file(d):
    return "Create hello.sh, a bash script that prints exactly: hello sakura. Make it executable.", lambda final: {
        "it runs": subprocess.run(["./hello.sh"], capture_output=True, text=True).stdout.strip() == "hello sakura"}


def search_my_docs(d):
    os.makedirs("notes")
    open("notes/leave.md", "w").write("Staff may carry over at most twelve days of annual leave into the next year, with their manager's approval.\n")
    open("notes/cargo.md", "w").write("The cargo desk handles inbound freight. Every shipment gets a manifest number before a bay is assigned.\n")
    return "Index my notes folder with rag, then use it to tell me how many vacation days roll over, and which file says so.", lambda final: {
        "the answer": bool(re.search(r"twelve|\b12\b", final, re.I)), "the source": "leave.md" in final}


def make_docx(d):
    return "Make report.docx: a Word document titled Quarterly Report with one paragraph saying revenue rose 12 percent.", lambda final: {
        "a real .docx with the text": os.path.exists("report.docx") and "Quarterly Report" in zip_text("report.docx", "word/document") and "12" in zip_text("report.docx", "word/document")}


def make_xlsx(d):
    open("sales.csv", "w").write("item,qty,price\napple,3,2.5\npear,4,1.5\n")
    return "Turn sales.csv into sales.xlsx, with a total column that's qty times price as a formula.", lambda final: {
        "a real .xlsx with the data": os.path.exists("sales.xlsx") and "apple" in zip_text("sales.xlsx", "xl/"),
        "with formulas": os.path.exists("sales.xlsx") and bool(re.search(rb"<f>", b"".join(zipfile.ZipFile("sales.xlsx").read(n) for n in zipfile.ZipFile("sales.xlsx").namelist() if n.startswith("xl/worksheets/"))))}


def make_pptx(d):
    return "Make deck.pptx: three slides, titled Plan, Progress and Risks.", lambda final: {
        "a real .pptx with three slides": os.path.exists("deck.pptx") and sum(bool(re.fullmatch(r"ppt/slides/slide\d+\.xml", n)) for n in zipfile.ZipFile("deck.pptx").namelist()) == 3,
        "with the titles": os.path.exists("deck.pptx") and all(t in zip_text("deck.pptx", "ppt/slides/") for t in ("Plan", "Progress", "Risks"))}


def make_pdf(d):
    open("notes.md", "w").write("# Field notes\n\nThe river rose two metres in October.\n")
    return "Turn notes.md into notes.pdf.", lambda final: {
        "a real PDF with the text": os.path.exists("notes.pdf") and "river rose" in subprocess.run(["pdftotext", "notes.pdf", "-"], capture_output=True, text=True).stdout}


CASES = {"edit-a-function": edit_a_function, "find-in-big-file": find_in_big_file, "new-file": new_file, "search-my-docs": search_my_docs,
         "make-docx": make_docx, "make-xlsx": make_xlsx, "make-pptx": make_pptx, "make-pdf": make_pdf}


def run(name, fn, args):
    with tempfile.TemporaryDirectory(prefix="sakura-tools-") as d:
        os.chdir(d)
        prompt, grade = fn(d)
        env = dict(os.environ, SAKURA_MEMORY_DIR=os.path.join(d, ".m"), SAKURA_TOOLS_DIR=os.path.join(d, ".t"), SAKURA_RAG_DB=os.path.join(d, ".rag.db"))
        t0 = time.time()
        cmd = ["sakura-launch", "--exec", "--skip-git-repo-check", "--json", prompt]
        try:
            out = subprocess.run(cmd, cwd=d, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=args.timeout).stdout
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        final, cmds, failed = "", [], 0
        for line in out.splitlines():
            try:
                item = json.loads(line).get("item", {})
            except ValueError:
                continue
            if item.get("type") == "agent_message" and item.get("text"):
                final = item["text"]
            if item.get("type") == "command_execution" and item.get("exit_code") is not None:
                cmds.append(re.sub(r"^/bin/bash -lc\s+['\"]?", "", item["command"])[:60].replace("\n", " "))
                failed += item["exit_code"] != 0
        try:
            checks = grade(final)
        except Exception as e:
            checks = {f"grading failed: {e}": False}
        os.chdir("/")
    ok = all(checks.values())
    print(f"{'PASS' if ok else 'FAIL'} {name} {time.time() - t0:.0f}s, {len(cmds)} cmds, {failed} failed {checks}\n   used: {cmds[:8]}\n   said: {final[:150]!r}", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    results = [run(n, f, a) for n, f in CASES.items() if not a.only or a.only == n]
    print(f"{sum(results)}/{len(results)}")


if __name__ == "__main__":
    main()
