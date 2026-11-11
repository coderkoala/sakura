#!/usr/bin/env python3
"""paper: letters and bills from templates in English and नेपाली, graded by what lands on disk, never by what the tool says of itself.
Amounts in words against hand-checked values; VAT and totals against sums worked by hand on awkward amounts; the PDF by the text
pdftotext gets back out of it and the fonts pdffonts finds inside; the register by its lines after several runs, a deleted line
and four runs at once; me.toml by its mode bits; `paper fill` by the fields pypdf reads back and the form's own bytes; Bikram
Sambat by dates that are a matter of record. A check whose converter or font isn't on this machine is SKIPPED, not passed.

  evals/paper.py              every case
  evals/paper.py --only NAME  one of: words vat templates refuse render nofont register me fill bs hledger
No model, no network.
"""

import argparse
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PAPER = os.path.join(ROOT, "bin", "paper")
SKIP = object()
NOW = "2026-11-11"


def run(args, tmp, cwd=None, extra=None, stdin=None, timeout=300):
    env = dict(os.environ, SAKURA_HOME=os.path.join(tmp, "home"), SAKURA_PAPER_NOW=NOW)
    env.update(extra or {})
    return subprocess.run(
        [PAPER, *args],
        env=env,
        cwd=cwd or tmp,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def squash(text):
    """Text as compared across a PDF: NFC, and no whitespace at all (pdftotext puts stray spaces inside Devanagari clusters)."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def me(tmp, **kv):
    for k, v in kv.items():
        run(["me", "set", k, v], tmp)


def details(tmp):
    me(
        tmp,
        name="Sita Kumari Shrestha",
        name_ne="सीता कुमारी श्रेष्ठ",
        address="Baneshwor-10, Kathmandu",
        address_ne="बानेश्वर-१०, काठमाडौँ",
        pan="601234567",
        phone="9841000000",
        email="sita@example.com",
        business="Himal Traders",
        business_ne="हिमाल ट्रेडर्स",
        bank_account="0123456789012345",
    )


def module():
    loader = importlib.machinery.SourceFileLoader("paper_tool", PAPER)
    spec = importlib.util.spec_from_loader("paper_tool", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# Every value below was written out by hand, not produced by the tool.
WORDS = [
    ("0", "Rupees Zero Only", "रुपैयाँ शून्य मात्र"),
    ("1", "Rupees One Only", "रुपैयाँ एक मात्र"),
    ("19", "Rupees Nineteen Only", "रुपैयाँ उन्नाइस मात्र"),
    ("99", "Rupees Ninety-Nine Only", "रुपैयाँ उनान्सय मात्र"),
    ("100", "Rupees One Hundred Only", "रुपैयाँ एक सय मात्र"),
    ("110", "Rupees One Hundred Ten Only", "रुपैयाँ एक सय दश मात्र"),
    ("2083", "Rupees Two Thousand Eighty-Three Only", "रुपैयाँ दुई हजार त्रियासी मात्र"),
    ("100000", "Rupees One Lakh Only", "रुपैयाँ एक लाख मात्र"),
    ("1,00,000", "Rupees One Lakh Only", "रुपैयाँ एक लाख मात्र"),
    ("1000001", "Rupees Ten Lakh One Only", "रुपैयाँ दश लाख एक मात्र"),
    (
        "1,23,45,678",
        "Rupees One Crore Twenty-Three Lakh Forty-Five Thousand Six Hundred Seventy-Eight Only",
        "रुपैयाँ एक करोड तेइस लाख पैँतालीस हजार छ सय अठहत्तर मात्र",
    ),
    ("1000000000", "Rupees One Hundred Crore Only", "रुपैयाँ एक अर्ब मात्र"),
    ("0.05", "Rupees Zero and Paisa Five Only", "रुपैयाँ शून्य र पैसा पाँच मात्र"),
    (
        "1234.50",
        "Rupees One Thousand Two Hundred Thirty-Four and Paisa Fifty Only",
        "रुपैयाँ एक हजार दुई सय चौँतीस र पैसा पचास मात्र",
    ),
    (
        "१२३४.५",
        "Rupees One Thousand Two Hundred Thirty-Four and Paisa Fifty Only",
        "रुपैयाँ एक हजार दुई सय चौँतीस र पैसा पचास मात्र",
    ),
    (
        "999999.99",
        "Rupees Nine Lakh Ninety-Nine Thousand Nine Hundred Ninety-Nine and Paisa Ninety-Nine Only",
        "रुपैयाँ नौ लाख उनान्सय हजार नौ सय उनान्सय र पैसा उनान्सय मात्र",
    ),
]
NE_SPOT = {
    11: "एघार",
    15: "पन्ध्र",
    21: "एक्काइस",
    25: "पच्चीस",
    29: "उनन्तीस",
    36: "छत्तीस",
    39: "उनन्चालीस",
    42: "बयालीस",
    49: "उनन्चास",
    50: "पचास",
    55: "पचपन्न",
    59: "उनन्साठी",
    60: "साठी",
    66: "छयसट्ठी",
    69: "उनन्सत्तरी",
    70: "सत्तरी",
    75: "पचहत्तर",
    79: "उनासी",
    80: "असी",
    84: "चौरासी",
    89: "उनान्नब्बे",
    90: "नब्बे",
    95: "पन्चानब्बे",
}
EN_UNITS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
EN_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def read_back(words, small, units):
    """Words → the number, by this eval's own reading: a running group, multiplied out at each unit word."""
    total = group = 0
    for w in words.split():
        if w in units:
            if units[w] == 100:
                group *= 100
            else:
                total, group = total + group * units[w], 0
        else:
            group += small[w]
    return total + group


def words(tmp):
    got = {}
    for amount, en, ne in WORDS:
        got[amount] = (
            run(["words", amount, "--lang", "en"], tmp)
            .stdout.strip()
            .split("  ", 1)[-1],
            run(["words", amount, "--lang", "ne"], tmp)
            .stdout.strip()
            .split("  ", 1)[-1],
        )
    m = module()
    en_small = {w: i for i, w in enumerate(EN_UNITS)}
    en_small.update(
        {f"{t}-{EN_UNITS[u]}": v + u for t, v in EN_TENS.items() for u in range(1, 10)}
    )
    en_small.update(EN_TENS)
    ne_small = {m.words_ne(i): i for i in range(100)}
    sample = (
        list(range(0, 1200))
        + [10**k + d for k in range(3, 13) for d in (-1, 0, 1, 7)]
        + [(i * 7919 * 104729) % 10**12 for i in range(1, 600)]
    )
    en_ok = all(
        read_back(
            m.words_en(n),
            en_small,
            {"hundred": 100, "thousand": 1000, "lakh": 10**5, "crore": 10**7},
        )
        == n
        for n in sample
        if n < 10**9
    )
    ne_ok = all(
        read_back(
            m.words_ne(n),
            ne_small,
            {
                "सय": 100,
                "हजार": 1000,
                "लाख": 10**5,
                "करोड": 10**7,
                "अर्ब": 10**9,
                "खर्ब": 10**11,
            },
        )
        == n
        for n in sample
    )
    return {
        "English amounts in words match the hand-written table (0, 1, 19, 100, 1,00,000, 1,23,45,678, paisa)": all(
            got[a][0] == en for a, en, _ in WORDS
        ),
        "Nepali amounts in words match the hand-written table, in लाख and करोड": all(
            got[a][1] == ne for a, _, ne in WORDS
        ),
        "the hundred Nepali number words are all different, and 23 spot values are the hand-checked ones": len(
            ne_small
        )
        == 100
        and all(m.words_ne(n) == w for n, w in NE_SPOT.items()),
        "English words read back to the same number for 1,800 values up to 100 crore": en_ok,
        "Nepali words read back to the same number for 1,800 values up to 10 खर्ब": ne_ok,
        "grouping is 12,34,567 and never 1,234,567": m.group(1234567) == "12,34,567"
        and m.group(999) == "999"
        and m.group(100000) == "1,00,000"
        and m.money(123456789) == "12,34,567.89",
        "a negative or malformed amount is refused": run(
            ["words", "-5"], tmp
        ).returncode
        != 0
        and run(["words", "12.345"], tmp).returncode != 0,
    }


def invoice_md(tmp, name, args, lang="en"):
    out = os.path.join(tmp, name)
    r = run(
        [
            "new",
            "invoice",
            "--lang",
            lang,
            "--set",
            "buyer=Ram Thapa",
            "-o",
            out,
            *args,
        ],
        tmp,
    )
    return (open(out, encoding="utf-8").read() if os.path.exists(out) else ""), r


def vat(tmp):
    details(tmp)
    items = [
        "--item",
        "Pens, blue,3,33.33",
        "--item",
        "Oil,1.5,333.33",
        "--item",
        "Screws,7,0.07",
    ]
    # by hand: 99.99 + 500.00 (499.995 rounds up) + 0.49 = 600.48; 13% = 78.0624 -> 78.06; total 678.54
    a, _ = invoice_md(tmp, "a.md", items)
    # 10% off: 60.048 -> 60.05; taxable 540.43; 13% = 70.2559 -> 70.26; total 610.69
    b, _ = invoice_md(tmp, "b.md", [*items, "--discount", "10%"])
    # half a paisa of VAT rounds up: 0.50 -> 0.065 -> 0.07; total 0.57
    c, _ = invoice_md(tmp, "c.md", ["--item", "Stamp,1,0.50"])
    # a figure floats get wrong: 12,34,567.89 * 13% = 1,60,493.8257 -> 1,60,493.83; total 13,95,061.72
    d, _ = invoice_md(tmp, "d.md", ["--item", "Machine,1,1234567.89"])
    p, _ = invoice_md(tmp, "p.md", [*items, "--pan-only"])
    n, _ = invoice_md(tmp, "n.md", [*items, "--ne-digits"], lang="ne")
    bad, rbad = invoice_md(tmp, "bad.md", ["--item", "Oil,1.5,333.335"])
    over, rover = invoice_md(tmp, "over.md", [*items, "--discount", "700"])
    reg = [
        l.split("\t")
        for l in open(
            os.path.join(tmp, "home", "paper", "register.tsv"), encoding="utf-8"
        )
        .read()
        .splitlines()
        if not l.startswith("#")
    ]
    return {
        "line amounts: 3 x 33.33 = 99.99, 1.5 x 333.33 = 500.00 (the half paisa goes up), 7 x 0.07 = 0.49": all(
            s in a for s in ("| 99.99 |", "| 500.00 |", "| 0.49 |", "| Pens, blue |")
        ),
        "subtotal 600.48, VAT 13% 78.06, total 678.54, and the words say so": "| Subtotal | 600.48 |"
        in a
        and "| VAT 13% | 78.06 |" in a
        and "**678.54**" in a
        and "Rupees Six Hundred Seventy-Eight and Paisa Fifty-Four Only" in a,
        "10% off first: discount 60.05, taxable 540.43, VAT 70.26, total 610.69": all(
            s in b
            for s in (
                "| Discount | 60.05 |",
                "| Taxable amount | 540.43 |",
                "| VAT 13% | 70.26 |",
                "**610.69**",
            )
        ),
        "half a paisa of VAT rounds up (0.50 -> VAT 0.07, total 0.57)": "| VAT 13% | 0.07 |"
        in c
        and "**0.57**" in c
        and "Rupees Zero and Paisa Fifty-Seven Only" in c,
        "12,34,567.89 + 13% = 13,95,061.72 exactly, grouped in lakhs": "| VAT 13% | 1,60,493.83 |"
        in d
        and "**13,95,061.72**" in d
        and "Rupees Thirteen Lakh Ninety-Five Thousand Sixty-One and Paisa Seventy-Two Only"
        in d,
        "--pan-only: no VAT line, total 600.48, the seller's number is called PAN": "VAT"
        not in p
        and "**600.48**" in p
        and "PAN No.: 601234567" in p,
        "with VAT the same number is called the VAT number": "VAT No.: 601234567" in a,
        "the Nepali bill has the same figures in Devanagari digits and words": "| मू.अ.कर १३% | ७८.०६ |"
        in n
        and "**६७८.५४**" in n
        and "रुपैयाँ छ सय अठहत्तर र पैसा चवन्न मात्र" in n
        and "मू.अ.कर दर्ता नं.: ६०१२३४५६७" in n
        and "INV-2083/84-" in n,
        "the register holds taxable, VAT and total for each bill": [
            r[4:7] for r in reg[:4]
        ]
        == [
            ["600.48", "78.06", "678.54"],
            ["540.43", "70.26", "610.69"],
            ["0.50", "0.07", "0.57"],
            ["1234567.89", "160493.83", "1395061.72"],
        ],
        "a rate with three decimals, or a discount bigger than the bill, is refused and nothing is written": rbad.returncode
        != 0
        and not bad
        and rover.returncode != 0
        and not over
        and len(reg) == 6,
    }


FILL = {
    "to_title": "प्रधानाध्यापक",
    "to_office": "श्री जनता माध्यमिक विद्यालय",
    "to_address": "ललितपुर",
    "subject": "चारित्रिक प्रमाणपत्र उपलब्ध गराइदिने सम्बन्धमा।",
    "body": "पहिलो अनुच्छेद।\nदोस्रो अनुच्छेद।",
    "from_date": "2026-11-12",
    "to_date": "bs:2083-07-28",
    "reason": "ज्वरो आएकाले आराम गर्नुपर्ने भएको छ।",
    "municipality": "काठमाडौँ महानगरपालिका",
    "ward_no": "10",
    "received_from": "राम बहादुर थापा",
    "amount": "1,23,456.50",
    "purpose": "फर्निचरको अग्रिम",
    "tenant": "हरि प्रसाद",
    "property": "फ्ल्याट २ख",
    "period": "कात्तिक",
    "employee": "गीता शर्मा",
    "position": "लेखापाल",
    "joined": "2020-01-15",
    "salary": "45000",
    "agent": "श्याम थापा",
    "buyer": "राम बहादुर थापा",
    "valid_until": "2026-12-31",
    "remarks": "काम सन्तोषजनक थियो।",
    "items": [["चामल", 2, "2333.33"]],
}
WANTED = [
    "application",
    "leave",
    "ward-request",
    "invoice",
    "receipt",
    "rent-receipt",
    "salary-certificate",
    "experience-letter",
    "authorization",
    "quotation",
]


def templates(tmp):
    details(tmp)
    src = os.path.join(tmp, "all.json")
    json.dump(FILL, open(src, "w"), ensure_ascii=False)
    shipped = sorted(os.listdir(os.path.join(ROOT, "templates", "paper")))
    m = module()
    texts, same_fields = {}, True
    for t in WANTED:
        for lang in ("en", "ne"):
            out = os.path.join(tmp, f"{t}.{lang}.md")
            run(["new", t, "--lang", lang, "--from", src, "--draft", "-o", out], tmp)
            texts[(t, lang)] = (
                open(out, encoding="utf-8").read() if os.path.exists(out) else ""
            )
        heads = [
            m.tomllib.loads(
                open(
                    os.path.join(ROOT, "templates", "paper", f"{t}.{lang}.md"),
                    encoding="utf-8",
                )
                .read()
                .split("+++\n")[1]
            )
            for lang in ("en", "ne")
        ]
        same_fields = (
            same_fields
            and list(heads[0]["fields"]) == list(heads[1]["fields"])
            and [f.get("required") for f in heads[0]["fields"].values()]
            == [f.get("required") for f in heads[1]["fields"].values()]
        )
    deva = re.compile("[%s-%s]" % (chr(0x0900), chr(0x097F)))
    lists = run(["list"], tmp).stdout
    # the user's own copy of a template replaces the shipped one
    mine = os.path.join(tmp, "home", "paper", "templates")
    os.makedirs(mine)
    open(os.path.join(mine, "leave.en.md"), "w").write(
        '+++\ntitle = "Mine"\n[fields]\nwho = {required = true}\n+++\nOVERRIDDEN for {{who}} on {{date_iso}}\n'
    )
    run(["new", "leave", "--set", "who=Asha", "-o", os.path.join(tmp, "mine.md")], tmp)
    broken = os.path.join(mine, "broken.en.md")
    open(broken, "w").write(
        '+++\ntitle = "Broken"\n[fields]\nwho = {required = true}\n+++\nHello {{who}} and {{nobody}}\n'
    )
    rb = run(
        ["new", "broken", "--set", "who=Asha", "-o", os.path.join(tmp, "broken.md")],
        tmp,
    )
    evil = os.path.join(tmp, "evil.md")
    run(
        [
            "new",
            "application",
            "--draft",
            "-o",
            evil,
            "--set",
            "to_title=The Principal",
            "--set",
            "to_office=X School",
            "--set",
            "subject=# *Big* [link](http://x) | pipe",
            "--set",
            "body=1. first\n- second\n> third <b>bold</b>",
        ],
        tmp,
    )
    evil_text = open(evil).read() if os.path.exists(evil) else ""
    plain = ""
    if shutil.which("pandoc") and evil_text:
        plain = subprocess.run(
            ["pandoc", "-f", m.PANDOC_FROM, "-t", "plain", "--wrap=none", evil],
            capture_output=True,
            text=True,
        ).stdout
    results = {
        "all ten templates ship in English and in Nepali": all(
            f"{t}.{lang}.md" in shipped for t in WANTED for lang in ("en", "ne")
        ),
        "each pair declares the same fields, required alike": same_fields,
        "every template fills in both languages": all(
            len(texts[k]) > 150 for k in texts
        ),
        "no {{ survives in any of the twenty": all(
            texts[k] and "{{" not in texts[k] for k in texts
        ),
        "the Nepali ones are written in Devanagari and carry the planted names": all(
            len(deva.findall(texts[(t, "ne")])) > 80 for t in WANTED
        )
        and "सीता कुमारी श्रेष्ठ" in texts[("application", "ne")]
        and "राम बहादुर थापा" in texts[("receipt", "ne")]
        and "हिमाल ट्रेडर्स" in texts[("invoice", "ne")],
        "the English ones use the plain saved details, not the _ne ones": "Sita Kumari Shrestha"
        in texts[("application", "en")]
        and "Himal Traders" in texts[("invoice", "en")],
        "amount in words inside the receipt, both languages": "Rupees One Lakh Twenty-Three Thousand Four Hundred Fifty-Six and Paisa Fifty Only"
        in texts[("receipt", "en")]
        and "रुपैयाँ एक लाख तेइस हजार चार सय छपन्न र पैसा पचास मात्र"
        in texts[("receipt", "ne")],
        "a date given as bs:2083-07-28 comes out in both calendars": "14 November 2026"
        in texts[("leave", "en")]
        and "2083 कात्तिक 28 गते" in texts[("leave", "ne")],
        "list names every template under each language": all(
            lists.count(f"  {t} ") == 2 for t in WANTED
        )
        and "नेपाली (ne)" in lists
        and "English (en)" in lists,
        "a template in the user's folder replaces the shipped one": open(
            os.path.join(tmp, "mine.md")
        )
        .read()
        .strip()
        == f"OVERRIDDEN for Asha on {NOW}"
        if os.path.exists(os.path.join(tmp, "mine.md"))
        else False,
        "a template naming a field it never declared is refused, not half-filled": rb.returncode
        != 0
        and not os.path.exists(os.path.join(tmp, "broken.md"))
        and "nobody" in rb.stderr
        and "Traceback" not in rb.stderr,
    }
    if plain:
        results[
            "what the user types stays text: no heading, list, link or table grows out of a value"
        ] = (
            "Subject: # *Big* [link](http://x) | pipe" in plain
            and "1. first" in plain
            and "- second" in plain
            and "> third <b>bold</b>" in plain
        )
    else:
        results["what the user types stays text (needs pandoc to read it back)"] = SKIP
    return results


def refuse(tmp):
    details(tmp)
    out = os.path.join(tmp, "leave.pdf")
    before = sorted(os.listdir(tmp))
    r = run(
        ["new", "leave", "--lang", "ne", "--set", "to_title=प्रबन्धक", "-o", out], tmp
    )
    r_default = run(["new", "leave", "--lang", "ne", "--set", "to_title=प्रबन्धक"], tmp)
    after = sorted(os.listdir(tmp))
    inv = os.path.join(tmp, "inv.md")
    r2 = run(["new", "invoice", "-o", inv], tmp)
    r3 = run(["new", "invoice", "--set", "buyer=Ram", "-o", inv], tmp)
    typo = run(["new", "leave", "--set", "to_titel=x", "-o", out], tmp)
    keep = os.path.join(tmp, "keep.md")
    open(keep, "w").write("mine\n")
    r4 = run(
        ["new", "invoice", "--set", "buyer=Ram", "--item", "x,1,10", "-o", keep], tmp
    )
    home = os.path.join(tmp, "home", "paper")
    f = run(["fields", "leave", "--lang", "ne"], tmp).stdout
    return {
        "a missing required field refuses (exit 1) and names every one that's missing": r.returncode
        == 1
        and all(k in r.stderr for k in ("to_office", "from_date", "to_date", "reason"))
        and "to_title " not in r.stderr.split("\n", 1)[-1],
        "and writes nothing: no document, no partial file": not os.path.exists(out)
        and after == before
        and r_default.returncode == 1,
        "an invoice without a buyer or without a line is refused the same way": r2.returncode
        == 1
        and "buyer" in r2.stderr
        and "--item" in r2.stderr
        and r3.returncode == 1
        and "--item" in r3.stderr
        and not os.path.exists(inv),
        "a mistyped --set key is refused rather than dropped": typo.returncode != 0
        and "to_titel" in typo.stderr,
        "an existing output file is not written over, and the refused bill takes no number": r4.returncode
        == 1
        and open(keep).read() == "mine\n"
        and not os.path.exists(os.path.join(home, "register.tsv")),
        "fields marks the required ones and shows which a saved detail answers": re.search(
            r"to_office\s+\* ", f
        )
        is not None
        and re.search(r"position\s+  ", f) is not None
        and "saved: सीता कुमारी श्रेष्ठ" in f,
    }


def pdf_text(path):
    return subprocess.run(
        ["pdftotext", path, "-"], capture_output=True, text=True
    ).stdout


def can_render():
    missing = [
        t for t in ("pandoc", "pdftotext", "pdffonts") if not shutil.which(t)
    ] + (
        []
        if shutil.which("libreoffice") or shutil.which("soffice")
        else ["libreoffice"]
    )
    return missing


def render(tmp):
    missing = can_render()
    if missing:
        return {f"rendering ({', '.join(missing)} not installed)": SKIP}
    details(tmp)
    m = module()
    en = os.path.join(tmp, "en.pdf")
    r = run(
        [
            "new",
            "application",
            "-o",
            en,
            "--set",
            "to_title=The Principal",
            "--set",
            "to_office=Janata Secondary School",
            "--set",
            "subject=Request for a character certificate",
            "--set",
            "body=I studied at this school until 2080.\nI need the certificate for a scholarship.",
        ],
        tmp,
    )
    en_text = pdf_text(en) if os.path.exists(en) else ""
    results = {
        "the English PDF's own text carries the planted name, the subject and the date in both calendars": r.returncode
        == 0
        and "Sita Kumari Shrestha" in en_text
        and "Request for a character certificate" in en_text
        and "11 November 2026 (25 Kartik 2083 BS)" in en_text
        and "{{" not in en_text,
        "it is one A4 page": "595"
        in subprocess.run(["pdfinfo", en], capture_output=True, text=True).stdout
        and "Pages:           1"
        in subprocess.run(["pdfinfo", en], capture_output=True, text=True).stdout
        if shutil.which("pdfinfo")
        else SKIP,
    }
    font = m.deva_font({})
    if not font:
        results[
            "the Nepali PDF (no Devanagari font installed: sudo apt-get install -y fonts-noto-core)"
        ] = SKIP
        return results
    src = os.path.join(tmp, "ne.json")
    json.dump(
        {
            "to_title": "प्रधानाध्यापक",
            "to_office": "श्री जनता माध्यमिक विद्यालय",
            "subject": "चारित्रिक प्रमाणपत्र उपलब्ध गराइदिने सम्बन्धमा।",
            "body": "म यस विद्यालयको पूर्व विद्यार्थी हुँ। छात्रवृत्तिका लागि प्रमाणपत्र आवश्यक परेको छ।",
        },
        open(src, "w"),
        ensure_ascii=False,
    )
    planted = [
        "सीता कुमारी श्रेष्ठ",
        "श्रीमान् प्रधानाध्यापकज्यू",
        "श्री जनता माध्यमिक विद्यालय",
        "चारित्रिक प्रमाणपत्र उपलब्ध गराइदिने सम्बन्धमा।",
        "छात्रवृत्तिका लागि प्रमाणपत्र आवश्यक परेको छ।",
        "अतः उपर्युक्त बेहोरा मनन गरी आवश्यक कारबाही गरिदिनुहुन सादर अनुरोध गर्दछु।",
        "2083 कात्तिक 25 गते",
        "बानेश्वर-१०, काठमाडौँ",
    ]
    ne, docx, md = (
        os.path.join(tmp, "ne.pdf"),
        os.path.join(tmp, "ne.docx"),
        os.path.join(tmp, "ne.md"),
    )
    rn = run(["new", "application", "--lang", "ne", "--from", src, "-o", ne], tmp)
    run(["new", "application", "--lang", "ne", "--from", src, "-o", docx], tmp)
    run(["new", "application", "--lang", "ne", "--from", src, "-o", md], tmp)
    ne_text = squash(pdf_text(ne)) if os.path.exists(ne) else ""
    fonts = (
        subprocess.run(["pdffonts", ne], capture_output=True, text=True).stdout
        if os.path.exists(ne)
        else ""
    )
    rows = [l.split() for l in fonts.splitlines()[2:]]
    name = font.replace(" ", "")
    xml = (
        zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8")
        if os.path.exists(docx)
        else ""
    )
    styles = (
        zipfile.ZipFile(docx).read("word/styles.xml").decode("utf-8")
        if os.path.exists(docx)
        else ""
    )
    xml_text = unicodedata.normalize("NFC", re.sub(r"<[^>]+>", "", xml))
    md_text = (
        unicodedata.normalize("NFC", open(md, encoding="utf-8").read())
        if os.path.exists(md)
        else ""
    )
    inv = os.path.join(tmp, "inv.pdf")
    run(
        [
            "new",
            "invoice",
            "--lang",
            "ne",
            "--ne-digits",
            "--set",
            "buyer=राम बहादुर थापा",
            "--item",
            "चामल (जिरा मसिनो),2,2333.33",
            "-o",
            inv,
        ],
        tmp,
    )
    inv_text = squash(pdf_text(inv)) if os.path.exists(inv) else ""
    results.update(
        {
            "the Nepali PDF gives back every planted Devanagari string, exactly (NFC, spacing aside)": rn.returncode
            == 0
            and all(squash(s) in ne_text for s in planted),
            "no {{ and no replacement boxes in it": bool(ne_text)
            and "{{" not in ne_text
            and "�" not in ne_text
            and "□" not in ne_text,
            f"the chosen font ({font}) is embedded in the PDF, and every font in it is embedded": any(
                name in r[0] for r in rows
            )
            and bool(rows)
            and all("yes" in r[-5:-2][:1] for r in rows),
            "the .docx carries the same strings and names the font for complex scripts": all(
                s in xml_text for s in planted
            )
            and f'w:cs="{font}"' in styles
            and "{{" not in xml_text,
            "the .md carries them too": all(s in md_text for s in planted)
            and "{{" not in md_text,
            "a Nepali invoice PDF: the items, the VAT and the total in words survive rendering": all(
                squash(s) in inv_text
                for s in (
                    "चामल (जिरा मसिनो)",
                    "४,६६६.६६",
                    "६०६.६७",
                    "५,२७३.३३",
                    "रुपैयाँ पाँच हजार दुई सय त्रिहत्तर र पैसा तेत्तीस मात्र",
                    "राम बहादुर थापा",
                    "हिमाल ट्रेडर्स",
                )
            ),
        }
    )
    return results


def nofont(tmp):
    if can_render() or not shutil.which("fc-list"):
        return {
            "refusing without a font (pandoc, libreoffice or fontconfig not installed)": SKIP
        }
    details(tmp)
    conf = os.path.join(tmp, "fonts.conf")
    open(conf, "w").write(
        f'<?xml version="1.0"?>\n<fontconfig><dir>{tmp}/nofonts</dir><cachedir>{tmp}/fc</cachedir></fontconfig>\n'
    )
    blind = {"FONTCONFIG_FILE": conf}
    out = os.path.join(tmp, "ne.pdf")
    args = [
        "new",
        "leave",
        "--lang",
        "ne",
        "--set",
        "to_title=प्रबन्धक",
        "--set",
        "to_office=हिमाल बैंक",
        "--set",
        "from_date=2026-11-12",
        "--set",
        "to_date=2026-11-13",
        "--set",
        "reason=बिरामी",
    ]
    r = run([*args, "-o", out], tmp, extra=blind)
    en = os.path.join(tmp, "en.pdf")
    r2 = run(
        [
            "new",
            "receipt",
            "--set",
            "received_from=राम बहादुर थापा",
            "--set",
            "amount=100",
            "--set",
            "purpose=advance",
            "-o",
            en,
        ],
        tmp,
        extra=blind,
    )
    md = os.path.join(tmp, "ne.md")
    r3 = run([*args, "-o", md], tmp, extra=blind)
    reg = os.path.join(tmp, "home", "paper", "register.tsv")
    return {
        "with no Devanagari font it refuses a Nepali PDF and gives the install line": r.returncode
        != 0
        and "fonts-noto-core" in r.stderr
        and not os.path.exists(out),
        "an English receipt with a Nepali name in it is refused too, and takes no number": r2.returncode
        != 0
        and not os.path.exists(en)
        and not os.path.exists(reg),
        "the .md still writes": r3.returncode == 0
        and os.path.exists(md)
        and "हिमाल बैंक" in open(md, encoding="utf-8").read(),
        "nothing half-made is left behind": not [
            x for x in os.listdir(tmp) if x.startswith(".paper")
        ],
    }


def register(tmp):
    details(tmp)
    reg = os.path.join(tmp, "home", "paper", "register.tsv")

    def bill(name, *extra, template="invoice"):
        out = os.path.join(tmp, name)
        base = (
            ["--set", "buyer=Ram Thapa", "--item", "x,1,100"]
            if template in ("invoice", "quotation")
            else [
                "--set",
                "received_from=Ram Thapa",
                "--set",
                "amount=100",
                "--set",
                "purpose=advance",
            ]
        )
        r = run(["new", template, *base, "-o", out, *extra], tmp)
        text = open(out).read() if os.path.exists(out) else ""
        found = re.search(r"No\.: ((?:INV|RCT|QTN)-\S+)", text)
        return found.group(1) if found else r.stderr.strip()

    def lines():
        return [
            l.split("\t")
            for l in open(reg, encoding="utf-8").read().splitlines()
            if l and not l.startswith("#")
        ]

    first, second = bill("1.md"), bill("2.md")
    draft = bill("d.md", "--draft")
    receipt = bill("r.md", template="receipt")
    quote = bill("q.md", template="quotation")
    # the last line goes missing from the register: its number must still never come back
    kept = open(reg, encoding="utf-8").read().splitlines()
    open(reg, "w", encoding="utf-8").write(
        "\n".join(l for l in kept if not l.startswith(second)) + "\n"
    )
    third = bill("3.md")
    old_year = bill("old.md", "--set", "date=2025-06-01")
    last_year, last_year2 = (
        bill("ly.md", "--set", "date=2025-08-01"),
        bill("ly2.md", "--set", "date=2026-03-05"),
    )
    env = dict(os.environ, SAKURA_HOME=os.path.join(tmp, "home"), SAKURA_PAPER_NOW=NOW)
    procs = [
        subprocess.Popen(
            [
                PAPER,
                "new",
                "invoice",
                "--set",
                f"buyer=Buyer {i}",
                "--item",
                "x,1,100",
                "-o",
                os.path.join(tmp, f"p{i}.md"),
            ],
            env=env,
            cwd=tmp,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for i in range(6)
    ]
    for p in procs:
        p.wait()
    together = sorted(
        re.search(r"INV-\S+", open(os.path.join(tmp, f"p{i}.md")).read()).group(0)
        for i in range(6)
    )
    # hold the lock ourselves: a bill must wait for it, not take a number behind its back
    held = os.path.join(tmp, "held.md")
    with open(os.path.join(tmp, "home", "paper", ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        waiting = subprocess.Popen(
            [
                PAPER,
                "new",
                "invoice",
                "--set",
                "buyer=Waits",
                "--item",
                "x,1,100",
                "-o",
                held,
            ],
            env=env,
            cwd=tmp,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        waited = (
            waiting.poll() is None and not os.path.exists(held) and len(lines()) == 13
        )
        fcntl.flock(lock, fcntl.LOCK_UN)
    waiting.wait(timeout=60)
    rows = lines()
    numbers = [r[0] for r in rows]
    me(tmp, fiscal_year_start="01-01")
    calendar = bill("cal.md")
    listing = run(["register", "2082/83"], tmp).stdout
    return {
        "the first two invoices are INV-2083/84-0001 and -0002 (11 November 2026 is in fiscal year 2083/84)": (
            first,
            second,
        )
        == ("INV-2083/84-0001", "INV-2083/84-0002"),
        "a --draft takes no number and enters nothing": "Invoice No.: DRAFT"
        in open(os.path.join(tmp, "d.md")).read()
        and not any(r[-1].endswith("/d.md") for r in rows)
        and "INV-" not in draft,
        "receipts and quotations count in their own series": (receipt, quote)
        == ("RCT-2083/84-0001", "QTN-2083/84-0001"),
        "a number whose register line was deleted is never given out again": third
        == "INV-2083/84-0003",
        "each fiscal year starts again at 0001 (1 June 2025 → 2081/82; 1 August 2025 and 5 March 2026 → 2082/83)": (
            old_year,
            last_year,
            last_year2,
        )
        == ("INV-2081/82-0001", "INV-2082/83-0001", "INV-2082/83-0002"),
        "six invoices written at the same moment get six different numbers, the next six": together
        == [f"INV-2083/84-{n:04d}" for n in range(4, 10)],
        "while another bill holds the lock, the next one waits and then takes -0010": waited
        and os.path.exists(held)
        and "INV-2083/84-0010" in open(held).read(),
        "no number appears twice in the register, and each line names date, party, total and file": len(
            numbers
        )
        == len(set(numbers))
        and all(
            len(r) == 8 and r[1][:2] == "20" and r[6] and os.path.exists(r[7])
            for r in rows
        ),
        "the register is plain text, one line a document": len(rows) == 14
        and open(reg, encoding="utf-8").read().startswith("#"),
        "fiscal_year_start 01-01 numbers by calendar year instead": calendar
        == "INV-2026-0001",
        "register 2082/83 lists only that year": listing.count("INV-2082/83-") == 2
        and "2083/84" not in listing,
    }


def me_case(tmp):
    details(tmp)
    path = os.path.join(tmp, "home", "paper", "me.toml")
    mode = stat.S_IMODE(os.stat(path).st_mode)
    shown = run(["me"], tmp).stdout
    listed = run(["fields", "invoice"], tmp).stdout
    got = run(["me", "get", "bank_account"], tmp).stdout.strip()
    me(tmp, quote='He said "hi" \\ there')
    import tomllib

    data = tomllib.load(open(path, "rb"))
    os.chmod(path, 0o644)
    me(tmp, extra="x")
    again = stat.S_IMODE(os.stat(path).st_mode)
    run(["me", "unset", "extra"], tmp)
    out = os.path.join(tmp, "i.md")
    run(
        [
            "new",
            "invoice",
            "--set",
            "buyer=Ram",
            "--item",
            "x,1,1",
            "--draft",
            "-o",
            out,
        ],
        tmp,
    )
    return {
        "me.toml is 0600 and its folder 0700": mode == 0o600
        and stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700,
        "it is 0600 again after a save, even if someone loosened it": again == 0o600,
        "the listing never shows an account number, a PAN or a phone whole: only the last four": "0123456789012345"
        not in shown
        and "2345" in shown
        and "601234567" not in shown
        and "9841000000" not in shown
        and "Sita Kumari Shrestha" in shown,
        "nor does `fields`, which shows what's saved": "601234567" not in listed
        and "4567" in listed,
        "`me get` gives one in full when asked": got == "0123456789012345",
        "the document itself carries the PAN whole": "601234567"
        in (open(out).read() if os.path.exists(out) else ""),
        "quotes and backslashes survive the file": data.get("quote")
        == 'He said "hi" \\ there'
        and data.get("name_ne") == "सीता कुमारी श्रेष्ठ",
        "unset forgets": "extra" not in tomllib.load(open(path, "rb")),
    }


def make_form(path):
    """A one-page AcroForm with the field names a real form would use. reportlab if it's here, else PyMuPDF."""
    names = [
        "Full Name",
        "Address",
        "PAN No.",
        "Mobile No",
        "Email",
        "Date",
        "Father's Name",
        "Bank Name",
        "Contact No",
    ]
    try:
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(path)
        for i, n in enumerate(names):
            c.drawString(60, 760 - 40 * i, n)
            c.acroForm.textfield(
                name=n,
                x=200,
                y=750 - 40 * i,
                width=300,
                height=22,
                value="already here" if n == "Contact No" else "",
                borderStyle="inset",
                forceBorder=True,
            )
        c.save()
        return names
    except ImportError:
        pass
    try:
        import pymupdf
    except ImportError:
        return None
    doc = pymupdf.open()
    page = doc.new_page()
    for i, n in enumerate(names):
        w = pymupdf.Widget()
        w.field_name, w.field_type, w.rect = (
            n,
            pymupdf.PDF_WIDGET_TYPE_TEXT,
            pymupdf.Rect(200, 60 + 40 * i, 500, 82 + 40 * i),
        )
        w.field_value = "already here" if n == "Contact No" else ""
        page.add_widget(w)
    doc.save(path)
    return names


def fill(tmp):
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"paper fill (pypdf not installed)": SKIP}
    form = os.path.join(tmp, "form.pdf")
    if not make_form(form):
        return {
            "paper fill (neither reportlab nor PyMuPDF here to make a test form)": SKIP
        }
    details(tmp)
    before = sha(form)
    dry = run(["fill", form], tmp)
    after_dry = sorted(x for x in os.listdir(tmp) if x.endswith(".pdf"))
    out = os.path.join(tmp, "done.pdf")
    go = run(["fill", form, "--map", "Bank Name=business", "--go", "-o", out], tmp)
    values = (
        {
            k: (v.get("/V") if hasattr(v, "get") else None)
            for k, v in (PdfReader(out).get_fields() or {}).items()
        }
        if os.path.exists(out)
        else {}
    )
    onto = run(["fill", form, "--go", "-o", form], tmp)
    auto = run(["fill", form, "--go"], tmp)
    made = [
        x
        for x in os.listdir(tmp)
        if x.endswith(".pdf") and x not in ("form.pdf", "done.pdf")
    ]
    return {
        "the dry run shows the mapping and writes nothing": dry.returncode == 0
        and after_dry == ["form.pdf"]
        and "Full Name" in dry.stdout
        and "<- name" in dry.stdout
        and "dry run" in dry.stdout,
        "the dry run masks the PAN and the phone": "601234567" not in dry.stdout
        and "9841000000" not in dry.stdout
        and "4567" in dry.stdout,
        "--go fills name, address, PAN, phone, email and today's date by the form's own field names": go.returncode
        == 0
        and values.get("Full Name") == "Sita Kumari Shrestha"
        and values.get("Address") == "Baneshwor-10, Kathmandu"
        and values.get("PAN No.") == "601234567"
        and values.get("Mobile No") == "9841000000"
        and values.get("Email") == "sita@example.com"
        and values.get("Date") == NOW,
        "a field it has no detail for (Father's Name) stays empty, and one already filled is left as it was": values.get(
            "Father's Name"
        )
        in (None, "")
        and values.get("Contact No") == "already here",
        "--map puts a saved detail on a field the table doesn't know": values.get(
            "Bank Name"
        )
        == "Himal Traders",
        "the form is byte-identical afterwards, even when -o names the form itself (refused)": sha(
            form
        )
        == before
        and onto.returncode != 0,
        "without -o the copy lands beside the form under a new name": auto.returncode
        == 0
        and len(made) == 1
        and sha(form) == before,
        "the saved details never stay behind in a temp file beside it": not [
            x for x in os.listdir(tmp) if x.endswith(".json")
        ],
    }


# Dates that are a matter of record, none of them taken from the tool or from the table it was built from:
# the new years; the 2015 earthquake (12 Baisakh 2072); the constitution (3 Ashwin 2072) and its anniversaries; Democracy Day
# (7 Falgun: 18 Feb 1951, 19 Feb 2025); Loktantra Day (11 Baisakh 2063); Republic Day (15 Jestha 2065); the 21 Falgun 2082 election.
BS_PAIRS = [
    ("1943-04-14", "2000-01-01"),
    ("1951-02-18", "2007-11-07"),
    ("2006-04-24", "2063-01-11"),
    ("2008-05-28", "2065-02-15"),
    ("2015-04-25", "2072-01-12"),
    ("2015-09-20", "2072-06-03"),
    ("2020-04-13", "2077-01-01"),
    ("2021-04-14", "2078-01-01"),
    ("2022-04-14", "2079-01-01"),
    ("2023-04-14", "2080-01-01"),
    ("2024-04-13", "2081-01-01"),
    ("2024-09-19", "2081-06-03"),
    ("2025-02-19", "2081-11-07"),
    ("2025-04-14", "2082-01-01"),
    ("2025-09-19", "2082-06-03"),
    ("2026-03-05", "2082-11-21"),
    ("2026-04-14", "2083-01-01"),
]


def bs(tmp):
    there = {
        ad: (re.search(r"= bs:(\S+)", run(["date", ad], tmp).stdout) or [None, None])[1]
        for ad, _ in BS_PAIRS
    }
    back = {b: run(["date", "bs:" + b], tmp).stdout.split(" ")[0] for _, b in BS_PAIRS}
    m = module()
    import datetime as dt

    day, ok, refused = m.BS_EPOCH, True, []
    last = m.BS_EPOCH + dt.timedelta(days=sum(sum(y) for y in m.bs_years()) - 1)
    while day <= last:  # every day of 84 years: there and back
        b = m.ad_to_bs(day)
        if b is None:
            refused.append(day)
        elif m.bs_to_ad(*b) != day:
            ok = False
        day += dt.timedelta(days=1)
    ok = (
        ok
        and len(refused) == 62
        and refused[0] == dt.date(2005, 4, 14)
        and refused[-1] == dt.date(2005, 6, 14)
        and last == dt.date(2027, 4, 13)
    )
    past = run(["date", "2027-05-01"], tmp)
    unsure = run(["date", "2005-05-01"], tmp)
    details(tmp)
    args = [
        "new",
        "leave",
        "--lang",
        "ne",
        "--set",
        "to_title=प्रबन्धक",
        "--set",
        "to_office=हिमाल बैंक",
        "--set",
        "from_date=2027-05-02",
        "--set",
        "to_date=2027-05-03",
        "--set",
        "reason=बिरामी",
        "--set",
        "date=2027-05-01",
    ]
    out, out2, out3 = (
        os.path.join(tmp, "late.md"),
        os.path.join(tmp, "nobs.md"),
        os.path.join(tmp, "added.md"),
    )
    run([*args, "-o", out], tmp)
    run(
        [
            "new",
            "leave",
            "--no-bs",
            "--set",
            "to_title=The Manager",
            "--set",
            "to_office=Himal Bank",
            "--set",
            "from_date=2026-11-12",
            "--set",
            "to_date=2026-11-13",
            "--set",
            "reason=fever",
            "-o",
            out2,
        ],
        tmp,
    )
    late = open(out).read() if os.path.exists(out) else ""
    inv = run(
        [
            "new",
            "invoice",
            "--set",
            "buyer=Ram",
            "--item",
            "x,1,1",
            "--set",
            "date=2027-05-01",
            "-o",
            os.path.join(tmp, "i.md"),
        ],
        tmp,
    )
    # the user adds the next year when its calendar is published
    open(os.path.join(tmp, "home", "paper", "bs-years.txt"), "w").write(
        "# from the published calendar\n2084 31 31 32 31 31 31 30 29 30 29 30 30\n"
    )
    run([*args, "-o", out3], tmp)
    added = open(out3).read() if os.path.exists(out3) else ""
    return {
        "17 dates of record convert AD → BS exactly (new years 2077-2083, the 2015 earthquake, Constitution, Democracy and Republic days)": all(
            there[ad] == b for ad, b in BS_PAIRS
        ),
        "and BS → AD": all(back[b] == ad for ad, b in BS_PAIRS),
        "every day from 1943 to the table's end goes there and back, except the two months of 2062 the sources disagree on (refused)": ok,
        "with no date given it is today's: 11 November 2026 = 25 Kartik 2083 by the table (not yet checked against the printed calendar)": run(
            ["date"], tmp
        ).stdout.startswith(f"{NOW} = bs:2083-07-25"),
        "a date past the table, and one in the disputed months, gets no BS date rather than a guess": past.returncode
        != 0
        and "bs:" not in past.stdout
        and unsure.returncode != 0
        and "bs:" not in unsure.stdout,
        "a letter dated past the table carries the Gregorian date alone": "ई.सं. 2027 मे 1"
        in late
        and "गते" not in late
        and "{{" not in late,
        "an invoice dated there is refused (its fiscal year can't be named), with the way out": inv.returncode
        != 0
        and "bs-years.txt" in inv.stderr
        and "fiscal_year_start" in inv.stderr,
        "--no-bs leaves the BS date out": "Date: 11 November 2026\n"
        in (open(out2).read() if os.path.exists(out2) else ""),
        "a year added to bs-years.txt is used": "2084 वैशाख 18 गते" in added,
    }


def hledger(tmp):
    if not shutil.which("hledger"):
        return {"the register as an hledger journal (hledger not installed)": SKIP}
    details(tmp)
    for i, extra in enumerate(
        (
            ["--item", "x,3,33.33", "--item", "y,1.5,333.33", "--item", "z,7,0.07"],
            ["--item", "x,1,1000", "--pan-only"],
        )
    ):
        run(
            [
                "new",
                "invoice",
                "--set",
                f"buyer=Buyer {i}",
                "-o",
                os.path.join(tmp, f"{i}.md"),
                *extra,
            ],
            tmp,
        )
    run(
        [
            "new",
            "receipt",
            "--set",
            "received_from=Buyer 0",
            "--set",
            "amount=678.54",
            "--set",
            "purpose=INV-2083/84-0001",
            "-o",
            os.path.join(tmp, "r.md"),
        ],
        tmp,
    )
    run(
        [
            "new",
            "quotation",
            "--set",
            "buyer=Nobody",
            "--item",
            "x,1,5",
            "-o",
            os.path.join(tmp, "q.md"),
        ],
        tmp,
    )
    journal = run(["register", "--hledger"], tmp).stdout
    h = lambda *a: subprocess.run(
        ["hledger", "-f", "-", *a], input=journal, capture_output=True, text=True
    )  # noqa: E731
    bal = h("bal", "--flat", "--no-total")
    amounts = {
        l.split()[-1]: " ".join(l.split()[:-1])
        for l in bal.stdout.splitlines()
        if l.strip()
    }
    return {
        "hledger reads it and every entry balances": h("check").returncode == 0
        and bal.returncode == 0,
        "sales 1,600.48, VAT owed 78.06, still receivable 1,000.00, cash 678.54": amounts.get(
            "income:sales"
        )
        == "NPR -1600.48"
        and amounts.get("liabilities:vat") == "NPR -78.06"
        and amounts.get("assets:receivable") == "NPR 1000.00"
        and amounts.get("assets:cash") == "NPR 678.54",
        "a quotation is not a transaction": "QTN" not in journal
        and "Nobody" not in journal,
    }


CASES = {
    "words": words,
    "vat": vat,
    "templates": templates,
    "refuse": refuse,
    "render": render,
    "nofont": nofont,
    "register": register,
    "me": me_case,
    "fill": fill,
    "bs": bs,
    "hledger": hledger,
}


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
