#!/usr/bin/env python3
"""Does ?tour describe a codebase from what's really in it? Graded by the files and lines it cites existing, the run and
test commands being the real ones, and the planted oddities being found. Never by how the tour reads.

  evals/tour.py                 every case
  evals/tour.py --only NAME
Needs the driver (sakura-launch brings it up).
"""
import argparse
import json
import os
import re
import subprocess
import tempfile


def write(d, files):
    for name, text in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


def project(d):
    write(d, {
        "README.md": "# shoplite\n\nA tiny order service: prices, tax and invoices.\n\nRun the tests with `make test`.\n",
        "Makefile": "test:\n\tpython3 -m unittest -q\n\nrun:\n\tpython3 -m shoplite.server\n",
        "shoplite/__init__.py": "",
        "shoplite/price.py": "TAX_RATE = 0.13  # Nepal VAT\n\n\ndef total(items, rate=TAX_RATE):\n    \"\"\"Sum of the items, with tax.\"\"\"\n    return round(sum(items) * (1 + rate), 2)\n",
        "shoplite/invoice.py": "from shoplite.price import total\n\n\ndef render(order):\n    # TODO: the currency is hard-coded; the customer's country should decide it\n"
                               "    lines = [f\"{name}: Rs {amount}\" for name, amount in order]\n    lines.append(f\"total: Rs {total(a for _, a in order)}\")\n    return \"\\n\".join(lines)\n",
        "shoplite/server.py": "import http.server\nfrom shoplite.invoice import render\n\n\nclass H(http.server.BaseHTTPRequestHandler):\n    def do_GET(self):\n"
                              "        body = render([('tea', 100), ('sugar', 50)]).encode()\n        self.send_response(200)\n        self.end_headers()\n        self.wfile.write(body)\n\n\n"
                              "if __name__ == '__main__':\n    http.server.HTTPServer(('127.0.0.1', 8080), H).serve_forever()\n",
        "tests/__init__.py": "",
        "tests/test_price.py": "import unittest\nfrom shoplite.price import total\n\n\nclass T(unittest.TestCase):\n    def test_total(self):\n        self.assertEqual(total([100]), 113.0)\n",
        "legacy/old_billing.py": "# HACK: kept for the 2019 importer, nothing calls this\ndef bill(x):\n    return x * 1.1\n",
    })
    subprocess.run("git init -q -b main . && git config user.email t@t && git config user.name t && git add . && git commit -qm 'shoplite' "
                   "&& echo '# shoplite' >> shoplite/invoice.py && git commit -qam 'invoice tweak' && echo '' >> shoplite/invoice.py && git commit -qam 'invoice again'",
                   shell=True, cwd=d, check=True, capture_output=True)


def tour(d, *words, timeout=900):
    r = subprocess.run(["sakura-tour", "--exec", "--json", d, *words], cwd=os.path.expanduser("~"), stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    commands, answer = [], ""
    for line in r.stdout.splitlines():
        try:
            item = json.loads(line).get("item", {})
        except ValueError:
            continue
        if item.get("type") == "command_execution":
            commands.append(item.get("command", ""))
        elif item.get("type") == "agent_message":
            answer = item.get("text", "")
    print("  ran:", " | ".join(c[-80:] for c in commands)[-700:])
    print("  said:", answer[-700:].replace("\n", " "))
    return commands, answer


def cited(answer, d):
    """(files cited that exist, files cited that don't). A citation is path or path:line."""
    names = set(re.findall(r"(?<![\w/])((?:[\w.-]+/)*[\w-]+\.(?:py|md|txt|toml|json|sh|yml|yaml|cfg|ini))(?::\d+)?", answer))
    names = {n for n in names if n not in ("README.md",) or True}
    exist = {n for n in names if os.path.exists(os.path.join(d, n))}
    return exist, names - exist


def line_citations_true(answer, d):
    """Every path:line cited points at a line that exists and isn't blank."""
    ok = bad = 0
    for path, line in re.findall(r"((?:[\w.-]+/)*[\w-]+\.py):(\d+)", answer):
        try:
            lines = open(os.path.join(d, path)).read().splitlines()
        except OSError:
            bad += 1
            continue
        n = int(line)
        if 1 <= n <= len(lines) and lines[n - 1].strip():
            ok += 1
        else:
            bad += 1
    return ok, bad


def walkthrough(d):
    project(d)
    commands, answer = tour(d)
    exist, missing = cited(answer, d)
    ok, bad = line_citations_true(answer, d)
    low = answer.lower()
    return {
        "it cites at least three real files": len(exist) >= 3,
        "it invents no files": not missing,
        "its line numbers point at real lines": ok >= 1 and bad == 0,
        "it gives the real test command": "make test" in low or "python3 -m unittest" in low,
        "it found the TODO or the HACK": "currency" in low or "todo" in low or "old_billing" in low or "hack" in low,
        "it read files rather than guessing": any(("view_file" in c or "cat " in c or "sed -n" in c or "rg " in c) for c in commands),
    }


def question(d):
    project(d)
    commands, answer = tour(d, "where is the tax rate set, and what is it?")
    low = answer.lower()
    exist, missing = cited(answer, d)
    return {
        "it answers with the file": "price.py" in low,
        "it gives the value": "0.13" in answer or "13%" in answer or "13 %" in answer,
        "it invents no files": not missing,
    }


CASES = {"walkthrough": walkthrough, "question": question}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    passed = total = 0
    for name, case in CASES.items():
        if args.only and args.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "shoplite")
            os.mkdir(work)
            print(f"\n== {name}", flush=True)
            for check, ok in case(work).items():
                print(f"  {'ok  ' if ok else 'FAIL'} {check}", flush=True)
                total += 1
                passed += bool(ok)
    print(f"\ntour: {passed}/{total}")


if __name__ == "__main__":
    main()
