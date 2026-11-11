#!/usr/bin/env python3
"""sakura-map, the repo map: graded on planted repositories, never by what the tool says about itself. The ranking by a
project where one module is imported everywhere and one script is referenced by nothing; line numbers by where this
eval wrote each definition; the budget by counting characters; ignoring by files planted behind .gitignore, vendor/
and a generated header; the cache by an edit hidden behind an unchanged mtime and size; the extractors by a snippet per
language with the names and lines it must (and must not) yield; the hook by its stdout for planted prompts.

  evals/map.py              every case
  evals/map.py --only NAME  one of: rank lines aim budget ignored broken cache big languages ctags hook tour
No model, no network. ctags is SKIPPED when universal-ctags isn't installed (it isn't a pass).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
MAP = os.path.join(ROOT, "bin", "sakura-map")
HOOK = os.path.join(ROOT, "hooks", "repo_map.py")
SKIP = object()


def run(args, env=None, cwd=None, stdin=None, timeout=180):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(
        args,
        env=e,
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def write(d, files):
    for name, text in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def commit(d):
    subprocess.run(
        "git init -q -b main . && git config user.email t@t && git config user.name t && git add -A && git commit -qm planted",
        shell=True,
        cwd=d,
        check=True,
        capture_output=True,
    )


def env_for(tmp, **more):
    """A cache, a home and a runtime dir of this eval's own; the built-in extractors unless a case asks for ctags."""
    e = {
        "SAKURA_MAP_CACHE": os.path.join(tmp, "cache"),
        "SAKURA_HOME": os.path.join(tmp, "home"),
        "XDG_RUNTIME_DIR": os.path.join(tmp, "run"),
        "SAKURA_MAP_SOURCE": "builtin",
    }
    os.makedirs(e["XDG_RUNTIME_DIR"], exist_ok=True)
    e.update(more)
    return e


def mapped(d, env, *args):
    r = run([MAP, d, "--json", *args], env)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"files": [], "text": "", "stats": {}, "error": r.stderr}


def line_of(text, needle):
    """Where this eval planted a definition: the 1-based line holding `needle`, counted here, not by the tool."""
    for no, line in enumerate(text.split("\n"), 1):
        if (
            line.strip() == needle.strip() if needle.endswith("\n") else needle in line
        ):  # "...\n" means the whole line
            return no
    raise AssertionError(needle)


def symbol(data, path, name):
    for f in data["files"]:
        if f["path"] == path:
            for s in f["symbols"]:
                if s["name"] == name:
                    return s
    return None


# ---- the planted project: a Python core, a JS front end, a Laravel-shaped PHP corner ----------------------------------------

MONEY = '''"""Money for the whole shop: one place that rounds and formats."""
from decimal import Decimal

DEFAULT_CURRENCY = "NPR"


def round_half_up(amount):
    return Decimal(amount).quantize(Decimal("0.01"))


def format_money(amount, currency=DEFAULT_CURRENCY):
    return f"{currency} {round_half_up(amount)}"


class MoneyError(ValueError):
    pass
'''
INVOICE = """from shopkit.money import format_money, round_half_up, MoneyError


def invoice_number(sequence):
    return f"INV-{sequence:05d}"


class Invoice:
    def __init__(self, customer):
        self.customer = customer
        self.lines = []

    def add_line(self, label, amount):
        if amount < 0:
            raise MoneyError(label)
        self.lines.append((label, amount))

    def total(self):
        return round_half_up(sum(a for _, a in self.lines))

    def render_summary(self):
        return format_money(self.total())
"""
CUSTOMER = """from shopkit.money import format_money


class Customer:
    def __init__(self, name, credit_limit):
        self.name = name
        self.credit_limit = credit_limit

    def credit_label(self):
        return format_money(self.credit_limit)
"""
REPORT = """from shopkit.invoice import Invoice, invoice_number
from shopkit.customer import Customer
from shopkit.money import format_money, round_half_up


def monthly_report(invoices):
    grand = round_half_up(sum(i.total() for i in invoices))
    return [invoice_number(n) for n, _ in enumerate(invoices)], format_money(grand)


def top_customer(customers):
    return max(customers, key=lambda c: c.credit_limit) if customers else Customer("nobody", 0)
"""
APP = '''"""The HTTP entry point. The front end (web/api.js) calls it."""
from shopkit.report import monthly_report, top_customer
from shopkit.money import format_money


def serve_report(request):
    return {"report": monthly_report(request.invoices), "owed": format_money(request.owed), "top": top_customer(request.customers)}
'''
LEAF = '''"""Run by hand once a year. Nothing imports this."""
from shopkit.money import format_money


def purge_stale_exports(folder, older_than_days=400):
    print("freed", format_money(0), folder, older_than_days)


if __name__ == "__main__":
    purge_stale_exports("/tmp/exports")
'''
API_JS = """// talks to shopkit/app.py; amounts are formatted there (shopkit/money.py, format_money)
export async function fetchInvoice(id) {
  const res = await fetch(`/invoices/${id}`);
  return res.json();
}

export const fetchReport = async (month) => {
  return (await fetch(`/report/${month}`)).json();
};
"""
CART_JS = """import { fetchInvoice } from './api.js';
// rounding must match shopkit/money.py round_half_up

export function cartTotal(lines) {
  return lines.reduce((sum, l) => sum + l.amount, 0);
}

export class Cart {
  constructor() {
    this.lines = [];
  }

  addLine(item) {
    this.lines.push(item);
  }

  async checkout(id) {
    if (this.lines.length) {
      return fetchInvoice(id);
    }
  }
}
"""
VUE = """<template>
  <table><tr v-for="row in rows" :key="row.id"><td>{{ formatRow(row) }}</td></tr></table>
</template>

<script>
import { Cart, cartTotal } from './cart.js';
import { fetchReport } from './api.js';

export default {
  name: 'InvoiceTable',
  data() {
    return { rows: [], cart: new Cart() };
  },
  methods: {
    formatRow(row) {
      return `${row.label}: ${cartTotal([row])}`;
    },
    async reload(month) {
      this.rows = await fetchReport(month);
    },
  },
};
</script>
"""
ORDER_PHP = """<?php

namespace App\\Models;

// amounts are formatted by the Python side: shopkit/money.py format_money
class Order extends Model
{
    const STATUS_PAID = 'paid';

    public function total(): float
    {
        return $this->lines->sum('amount');
    }

    public static function findByNumber(string $number): ?self
    {
        return static::where('number', $number)->first();
    }
}
"""
CONTROLLER_PHP = """<?php

namespace App\\Http\\Controllers;

use App\\Models\\Order;

/** Wired in routes/web.php. The table is web/InvoiceTable.vue. */
class OrderController extends Controller
{
    public function index()
    {
        return view('orders', ['orders' => Order::all()]);
    }

    public function show(string $number)
    {
        if (! $order = Order::findByNumber($number)) {
            abort(404);
        }
        return view('order', ['order' => $order, 'total' => $order->total()]);
    }
}
"""
ROUTES_PHP = """<?php

use App\\Http\\Controllers\\OrderController;
use Illuminate\\Support\\Facades\\Route;

Route::get('/orders', [OrderController::class, 'index']);
Route::get('/orders/{number}', [OrderController::class, 'show'])->name('orders.show');
"""
PROJECT = {
    "README.md": "# shopkit\n\nInvoices and orders. scripts/purge_stale_exports.py is run by hand.\n",
    "shopkit/__init__.py": "",
    "shopkit/money.py": MONEY,
    "shopkit/invoice.py": INVOICE,
    "shopkit/customer.py": CUSTOMER,
    "shopkit/report.py": REPORT,
    "shopkit/app.py": APP,
    "scripts/purge_stale_exports.py": LEAF,
    "web/api.js": API_JS,
    "web/cart.js": CART_JS,
    "web/InvoiceTable.vue": VUE,
    "app/Models/Order.php": ORDER_PHP,
    "app/Http/Controllers/OrderController.php": CONTROLLER_PHP,
    "routes/web.php": ROUTES_PHP,
}
LEAF_PATH = "scripts/purge_stale_exports.py"


def project(d, git=True):
    os.makedirs(d, exist_ok=True)
    write(d, PROJECT)
    if git:
        commit(d)
    return d


def rank(tmp):
    d = project(os.path.join(tmp, "shopkit"))
    env = env_for(tmp)
    data = mapped(d, env)
    paths = [f["path"] for f in data["files"]]
    ranks = {f["path"]: f["rank"] for f in data["files"]}
    listed = [l.split()[-1] for l in run([MAP, d, "--files"], env).stdout.splitlines()]
    text = run([MAP, d], env).stdout
    blocks = [l for l in text.splitlines() if l and not l.startswith((" ", "#", "("))]
    return {
        "the module every file imports ranks first": paths[:1] == ["shopkit/money.py"]
        and listed[:1] == ["shopkit/money.py"],
        "and it opens the map": blocks[:1] == ["shopkit/money.py"],
        "the script nothing references ranks last, strictly below every other file": paths[
            -1:
        ]
        == [LEAF_PATH]
        and all(ranks[LEAF_PATH] < r for p, r in ranks.items() if p != LEAF_PATH),
        "every source file is in the ranking, once": sorted(paths)
        == sorted(p for p in PROJECT if not p.endswith((".md", "__init__.py"))),
        "the ranks are a distribution (they sum to 1)": abs(sum(ranks.values()) - 1)
        < 1e-6,
        "under the top file, the function most files call comes first": bool(
            data["files"]
        )
        and data["files"][0]["symbols"][0]["name"] == "format_money",
        "then the one fewer call, then the one only one file uses": [
            s["name"] for s in data["files"][0]["symbols"]
        ][:2]
        == ["format_money", "round_half_up"]
        and data["files"][0]["symbols"][-1]["name"]
        in ("MoneyError", "DEFAULT_CURRENCY"),
        "run with no PATH inside the repo, it maps the repo": run(
            [MAP, "--files"], env, cwd=os.path.join(d, "web")
        ).stdout.splitlines()[:1]
        == run([MAP, d, "--files"], env).stdout.splitlines()[:1],
    }


def lines(tmp):
    d = project(os.path.join(tmp, "shopkit"))
    data = mapped(d, env_for(tmp))
    want = [
        ("shopkit/money.py", "format_money", MONEY, "def format_money", "function"),
        ("shopkit/money.py", "MoneyError", MONEY, "class MoneyError", "class"),
        ("shopkit/money.py", "DEFAULT_CURRENCY", MONEY, "DEFAULT_CURRENCY =", "const"),
        ("shopkit/invoice.py", "total", INVOICE, "def total", "method"),
        ("shopkit/invoice.py", "Invoice", INVOICE, "class Invoice", "class"),
        ("web/cart.js", "cartTotal", CART_JS, "function cartTotal", "function"),
        ("web/cart.js", "Cart", CART_JS, "class Cart", "class"),
        ("web/cart.js", "checkout", CART_JS, "async checkout", "method"),
        ("web/api.js", "fetchReport", API_JS, "const fetchReport", "function"),
        ("web/InvoiceTable.vue", "formatRow", VUE, "formatRow(row) {", "method"),
        ("web/InvoiceTable.vue", "reload", VUE, "async reload", "method"),
        ("app/Models/Order.php", "Order", ORDER_PHP, "class Order", "class"),
        (
            "app/Models/Order.php",
            "findByNumber",
            ORDER_PHP,
            "function findByNumber",
            "method",
        ),
        (
            "app/Http/Controllers/OrderController.php",
            "show",
            CONTROLLER_PHP,
            "function show",
            "method",
        ),
        (
            "routes/web.php",
            "GET /orders/{number}",
            ROUTES_PHP,
            "'/orders/{number}'",
            "route",
        ),
    ]
    out = {}
    for path, name, text, needle, kind in want:
        s = symbol(data, path, name)
        out[f"{path}: {name} is a {kind} on line {line_of(text, needle)}"] = (
            bool(s) and s["line"] == line_of(text, needle) and s["kind"] == kind
        )
    shown = run([MAP, d, "--budget", "20000"], env_for(tmp)).stdout
    out["the map prints that line number beside the signature"] = (
        f"  {line_of(MONEY, 'def format_money')}: def format_money(amount, currency=DEFAULT_CURRENCY)\n"
        in shown
    )
    out["a method says which class it's in"] = (
        f"  {line_of(INVOICE, 'def total')}: def total(self)  (Invoice)\n" in shown
    )
    names = {s["name"] for f in data["files"] for s in f["symbols"]}
    out["statements aren't definitions (if, constructor, data, fetch)"] = not names & {
        "if",
        "constructor",
        "data",
        "fetch",
        "abort",
        "view",
        "return",
    }
    return out


def aim(tmp):
    d = project(os.path.join(tmp, "shopkit"))
    env = env_for(tmp)
    plain = mapped(d, env)
    aimed = mapped(d, env, "--for", "invoice total")
    text = run([MAP, d, "--for", "invoice total"], env).stdout.splitlines()
    focus = mapped(d, env, "--focus", os.path.join(d, "web", "cart.js"))
    by_name = mapped(d, env, "--for", "the bug is in cart.js somewhere")
    php = mapped(d, env, "--for", "orders route")
    first = lambda data: data["files"][0]["path"] if data["files"] else None  # noqa: E731
    write(
        d,
        {
            "shopkit/customer.py": CUSTOMER
            + "\n\ndef customer_code(c):\n    return c.name[:3]\n"
        },
    )
    dirty = mapped(d, env)
    pos = lambda data, p: [f["path"] for f in data["files"]].index(p)  # noqa: E731
    rank_of = lambda data, p: next(f["rank"] for f in data["files"] if f["path"] == p)  # noqa: E731
    return {
        "without --for the invoice module isn't first": first(plain)
        != "shopkit/invoice.py",
        '--for "invoice total" puts the invoice module first': first(aimed)
        == "shopkit/invoice.py",
        "and its total function first under it": bool(aimed["files"])
        and aimed["files"][0]["symbols"][0]["name"] == "total",
        "the printed map opens with that file and that function": len(text) > 2
        and text[1] == "shopkit/invoice.py"
        and "def total(self)" in text[2],
        "--focus FILE puts that file first": first(focus) == "web/cart.js",
        "a file name in --for does the same": first(by_name) == "web/cart.js",
        "what the focused file imports rises with it": rank_of(focus, "web/api.js")
        > 1.5 * rank_of(plain, "web/api.js"),
        '--for "orders route" brings the routes file and its route to the top': first(
            php
        )
        in (
            "routes/web.php",
            "app/Models/Order.php",
            "app/Http/Controllers/OrderController.php",
        )
        and pos(php, "routes/web.php") <= 2
        and next(f for f in php["files"] if f["path"] == "routes/web.php")["symbols"][
            0
        ]["kind"]
        == "route",
        "a file edited in the working tree moves up": pos(dirty, "shopkit/customer.py")
        < pos(plain, "shopkit/customer.py"),
    }


def budget(tmp):
    d = project(os.path.join(tmp, "shopkit"))
    env = env_for(tmp)
    data = mapped(d, env)
    total = sum(len(f["symbols"]) for f in data["files"])
    full = run([MAP, d, "--budget", "100000"], env).stdout
    sizes = {}
    for n in list(range(120, 1500, 37)) + [415, 2000, 4000]:
        sizes[n] = run([MAP, d, "--budget", str(n)], env).stdout
    ns = sorted(sizes)
    # the edges: for every length the map came out at, a budget of exactly that must give it back, and one less must not
    exact = {len(t): t for t in sizes.values() if t}
    edge = {
        n: (
            run([MAP, d, "--budget", str(n)], env).stdout,
            run([MAP, d, "--budget", str(n - 1)], env).stdout,
        )
        for n in exact
    }
    over = [n for n, t in sizes.items() if len(t) > n] + [
        n for n, (at, below) in edge.items() if len(below) > n - 1
    ]
    hook_like = run([MAP, d, "--budget", "600", "--for", "invoice total"], env).stdout
    return {
        "never a character over, at 41 budgets from 120 to 4000 and one character under each length it produced": not over
        and len(exact) >= 8,
        "a budget of exactly a map's length gives that map": all(
            at == exact[n] for n, (at, below) in edge.items()
        ),
        "a bigger budget never shows less": all(
            len(sizes[a]) <= len(sizes[b]) for a, b in zip(ns, ns[1:])
        ),
        "it uses the room it's given (within 160 characters of a 700 budget)": 700 - 160
        <= len(run([MAP, d, "--budget", "700"], env).stdout)
        <= 700,
        "with room for everything, every definition is there": sum(
            1 for l in full.splitlines() if l.startswith("  ")
        )
        == total
        and total > 25,
        "a budget one short of everything leaves something out and says so": len(
            run([MAP, d, "--budget", str(len(full) - 1)], env).stdout
        )
        < len(full)
        and "more definitions"
        in run([MAP, d, "--budget", str(len(full) - 1)], env).stdout,
        "what's cut is the bottom of the ranking, not the top": sizes[415].splitlines()[
            1:2
        ]
        == ["shopkit/money.py"]
        and LEAF_PATH not in sizes[415],
        "the default is 4000": run([MAP, d], env).stdout == sizes[4000],
        "aimed and small, the aim survives the cut": "def total(self)" in hook_like
        and len(hook_like) <= 600,
        "a budget that isn't a number is refused": run(
            [MAP, d, "--budget", "lots"], env
        ).returncode
        == 2,
    }


def ignored(tmp):
    d = os.path.join(tmp, "shopkit")
    os.makedirs(d)
    write(d, PROJECT)
    planted = {
        ".gitignore": "secrets_local.py\n/generated/\n*.log\n",
        "secrets_local.py": "def ignored_secret_loader():\n    return 1\n",
        "generated/client.py": "def ignored_generated_client():\n    return 1\n",
        "vendor/acme/lib.php": "<?php\nfunction vendored_php_helper() { return 1; }\n",
        "node_modules/leftpad/index.js": "export function vendoredLeftPad(s) { return s; }\n",
        "web/app.min.js": "function minifiedBundle(){return 1}\n",
        "shopkit/schema_pb2.py": "def protobuf_generated_fn():\n    return 1\n",
        "shopkit/stubs.py": "# Code generated by stubgen. DO NOT EDIT.\ndef generated_header_fn():\n    return 1\n",
        "web/packed.js": "function onePackedLine(){return 1};"
        + "var a=1;" * 900
        + "\n",
        "shopkit/huge.py": "def huge_file_fn():\n    return 1\n"
        + "# padding\n" * 40000,
        "package-lock.json": '{"lockfileVersion": 3}\n',
        "shopkit/fresh.py": "from shopkit.money import format_money\n\n\ndef untracked_but_real(x):\n    return format_money(x)\n",
    }
    commit(d)
    write(d, planted)  # all untracked: only .gitignore and the skip rules keep them out
    os.symlink(
        os.path.join(d, "shopkit", "money.py"), os.path.join(d, "shopkit", "alias.py")
    )
    env = env_for(tmp)
    data = mapped(d, env)
    paths = {f["path"] for f in data["files"]}
    names = {s["name"] for f in data["files"] for s in f["symbols"]}
    text = run([MAP, d, "--budget", "100000"], env).stdout
    plain = os.path.join(
        tmp, "plain"
    )  # the same tree with no git: a walk, which still skips vendor/ and node_modules/
    shutil.copytree(d, plain, ignore=shutil.ignore_patterns(".git"), symlinks=True)
    walked = {s["name"] for f in mapped(plain, env)["files"] for s in f["symbols"]}
    return {
        "a .gitignored file is absent": "secrets_local.py" not in paths
        and "ignored_secret_loader" not in names
        and "ignored_secret" not in text,
        "a .gitignored directory is absent": "ignored_generated_client" not in names
        and not any(p.startswith("generated/") for p in paths),
        "vendor/ and node_modules/ are absent": not names
        & {"vendored_php_helper", "vendoredLeftPad"}
        and not any(p.startswith(("vendor/", "node_modules/")) for p in paths),
        "minified files are absent, by name and by shape": not names
        & {"minifiedBundle", "onePackedLine"},
        "generated files are absent, by name and by header": not names
        & {"protobuf_generated_fn", "generated_header_fn"},
        "a huge file and a symlink are absent": "huge_file_fn" not in names
        and "shopkit/alias.py" not in paths,
        "an untracked file that isn't ignored is there": "untracked_but_real" in names
        and "untracked_but_real" in text,
        "the real files are all still there": {
            "shopkit/money.py",
            "web/cart.js",
            "routes/web.php",
        }
        <= paths,
        "outside git, vendored and generated files are still skipped": "format_money"
        in walked
        and not walked
        & {
            "vendored_php_helper",
            "vendoredLeftPad",
            "minifiedBundle",
            "protobuf_generated_fn",
            "generated_header_fn",
            "huge_file_fn",
        },
    }


def broken(tmp):
    d = os.path.join(tmp, "shopkit")
    os.makedirs(d)
    write(d, PROJECT)
    bad = "from shopkit.money import format_money\n\n\ndef half_written(x:\n    return format_money(x\n\n\nclass StillFound:\n    def method_in_broken(self):\n        pass\n<<<<<<< HEAD\n"
    write(
        d,
        {
            "shopkit/broken.py": bad,
            "shopkit/binary.py": "def x():\n    pass\n\0\0\0",
            "web/odd.js": "function ( {{{{ \n}}} class \n",
            "shopkit/empty.py": "",
            "shopkit/latin.py": "def caf\u00e9_total():\n    return 1\n",
        },
    )
    with open(os.path.join(d, "shopkit", "bytes.py"), "wb") as f:
        f.write(b"def bad_bytes():\n    return '\xff\xfe'\n")
    commit(d)
    env = env_for(tmp)
    r = run([MAP, d, "--budget", "100000"], env)
    data = mapped(d, env)
    s = symbol(data, "shopkit/broken.py", "half_written")
    m = symbol(data, "shopkit/broken.py", "method_in_broken")
    return {
        "a Python file that doesn't parse doesn't stop the run": r.returncode == 0
        and "Traceback" not in r.stderr
        and "shopkit/money.py" in r.stdout,
        "its def lines are still found, on the right lines": bool(s)
        and s["line"] == line_of(bad, "def half_written")
        and bool(m)
        and m["line"] == line_of(bad, "def method_in_broken")
        and m["parent"] == "StillFound",
        "the module everyone imports still ranks first": data["files"][:1]
        and data["files"][0]["path"] == "shopkit/money.py",
        "garbage JavaScript, an empty file, NUL bytes and bad UTF-8 are survived": r.returncode
        == 0
        and symbol(data, "shopkit/bytes.py", "bad_bytes") is not None,
        "a non-ASCII name is read": symbol(data, "shopkit/latin.py", "caf\u00e9_total")
        is not None,
        "a path that isn't there is an error with a reason, not a trace": run(
            [MAP, os.path.join(tmp, "nope")], env
        ).returncode
        == 2
        and "Traceback" not in run([MAP, os.path.join(tmp, "nope")], env).stderr,
        "a folder with no source says so and exits 1": run(
            [MAP, tempfile.mkdtemp(dir=tmp)], env
        ).returncode
        == 1,
    }


def cache(tmp):
    d = project(
        os.path.join(tmp, "shopkit"), git=False
    )  # no git, so only the cache decides whether a file is read again
    env = env_for(tmp)
    cache_dir = env["SAKURA_MAP_CACHE"]
    args = [MAP, d, "--budget", "100000"]
    first = run(args, env).stdout
    made = os.listdir(cache_dir) if os.path.isdir(cache_dir) else []
    second = run(args, env).stdout
    path = os.path.join(d, "shopkit", "money.py")
    st = os.stat(path)
    with (
        open(path, "w") as f
    ):  # same length, same mtime: only something that re-reads the file could notice
        f.write(MONEY.replace("format_money", "format_cashx"))
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    same_size = os.stat(path).st_size == st.st_size
    hidden = run(args, env).stdout
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    touched = run(args, env).stdout
    with open(path, "a") as f:
        f.write("\n\ndef added_after_the_cache(x):\n    return x\n")
    os.utime(
        path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000)
    )  # same mtime as the last run: only the size differs
    grown = run(args, env).stdout
    os.remove(os.path.join(d, "web", "cart.js"))
    removed = run(args, env).stdout
    for name in os.listdir(cache_dir):
        with open(os.path.join(cache_dir, name), "w") as f:
            f.write("{ not json")
    corrupt = run(args, env)
    open(os.path.join(tmp, "file-not-dir"), "w").close()
    unwritable = run(
        args, dict(env, SAKURA_MAP_CACHE=os.path.join(tmp, "file-not-dir", "x"))
    )
    # a repo big enough to time: reading 1,200 files against stat-ing them
    big = synthetic(os.path.join(tmp, "big"), 1200)
    benv = dict(env, SAKURA_MAP_CACHE=os.path.join(tmp, "bigcache"))
    t0 = time.monotonic()
    cold = run([MAP, big], benv).stdout
    t1 = time.monotonic()
    warm = run([MAP, big], benv).stdout
    t2 = time.monotonic()
    print(f"  cache: 1,200 files cold {t1 - t0:.2f}s, warm {t2 - t1:.2f}s")
    return {
        "the first run leaves a cache on disk, under the cache dir and nowhere else": len(
            made
        )
        == 1
        and not os.path.exists(os.path.join(d, ".sakura")),
        "the second run prints the same map": first == second
        and "format_money" in first,
        "an edit hidden behind the same mtime and size is not seen: the cache was used": same_size
        and hidden == first,
        "a new mtime invalidates it": "format_cashx" in touched
        and "def format_money" not in touched,
        "a new size alone invalidates it": "added_after_the_cache" in grown,
        "a deleted file leaves the map": "web/cart.js" in grown
        and "web/cart.js" not in removed,
        "a corrupt cache is rebuilt, not trusted": corrupt.returncode == 0
        and corrupt.stdout == removed,
        "a cache dir that can't be made costs nothing but time": unwritable.returncode
        == 0
        and unwritable.stdout == removed,
        "a warm run is faster than a cold one, with the same output": warm == cold
        and (t2 - t1) < (t1 - t0) * 0.8,
    }


def synthetic(d, n):
    """n small files in three languages. Every file uses core/ledger.py; each also calls its neighbour."""
    files = {
        "core/ledger.py": "class LedgerEntry:\n    def post_entry(self, amount):\n        return amount\n\n\ndef ledger_balance(entries):\n    return sum(entries)\n"
    }
    for i in range(n - 1):
        pkg = f"pkg{i % 40:02d}"
        if i % 3 == 0:
            files[f"{pkg}/mod_{i}.py"] = (
                f"from core.ledger import ledger_balance, LedgerEntry\n\n\ndef handler_{i}(rows):\n    return ledger_balance(rows) + helper_{i}(rows)\n\n\n"
                f"def helper_{i}(rows):\n    return len(rows)\n\n\nclass Service{i}(LedgerEntry):\n    def run_{i}(self):\n        return handler_{max(i - 3, 0)}([])\n"
            )
        elif i % 3 == 1:
            files[f"{pkg}/widget_{i}.js"] = (
                f"// totals come from core/ledger.py ledger_balance\nexport function renderWidget{i}(rows) {{\n  return rows.length;\n}}\n\n"
                f"export class Widget{i} {{\n  draw(rows) {{\n    return renderWidget{i}(rows) + renderWidget{max(i - 3, 1)}(rows);\n  }}\n}}\n"
            )
        else:
            files[f"{pkg}/Model{i}.php"] = (
                f"<?php\n// ledger_balance in core/ledger.py is the source of truth\nclass Model{i}\n{{\n    public function balance{i}()\n    {{\n"
                f"        return (new Model{max(i - 3, 2)})->balance{max(i - 3, 2)}();\n    }}\n}}\n"
            )
    write(d, files)
    return d


def big(tmp):
    d = synthetic(os.path.join(tmp, "big"), 3000)
    commit(d)
    env = env_for(tmp)
    t0 = time.monotonic()
    cold = run([MAP, d], env)
    t1 = time.monotonic()
    warm = run([MAP, d, "--for", "widget 1000"], env)
    t2 = time.monotonic()
    data = mapped(d, env)
    capped = run(
        [MAP, d, "--json"],
        dict(
            env,
            SAKURA_MAP_MAX_FILES="400",
            SAKURA_MAP_CACHE=os.path.join(tmp, "capcache"),
        ),
    )
    cap = json.loads(capped.stdout or "{}")
    capped_text = run(
        [MAP, d],
        dict(
            env,
            SAKURA_MAP_MAX_FILES="400",
            SAKURA_MAP_CACHE=os.path.join(tmp, "capcache"),
        ),
    )
    print(f"  big: 3,000 files cold {t1 - t0:.2f}s, warm and aimed {t2 - t1:.2f}s")
    return {
        "3,000 files, nothing cached: an answer within 20 seconds": cold.returncode == 0
        and (t1 - t0) < 20,
        "cached and aimed at a task: within 8 seconds": warm.returncode == 0
        and (t2 - t1) < 8,
        "all 3,000 files were ranked": len(data["files"]) == 3000,
        "the file all of them use ranks first": data["files"][0]["path"]
        == "core/ledger.py"
        and cold.stdout.splitlines()[1] == "core/ledger.py",
        "the map still fits the budget": 0 < len(cold.stdout) <= 4000,
        "aimed, the widget the task names is first": warm.stdout.splitlines()[1]
        == f"pkg{1000 % 40:02d}/widget_1000.js",
        "over the file limit it reads the limit, says how many it left, and still ranks": len(
            cap.get("files", [])
        )
        == 400
        and cap["stats"]["left_out"] == 2600
        and "2600 more source files" in capped_text.stderr
        and cap["files"][0]["path"] == "core/ledger.py",
    }


# ---- one snippet per language: (file, text, [(name, kind, text on its line)], [names that must not appear]) ------------------

SNIPPETS = {
    "python": (
        "snip.py",
        """import os

LIMIT_ROWS = 50
lower = 1


async def fetch_rows(conn, *, limit: int = LIMIT_ROWS) -> list:
    def inner():
        pass
    return []


class Repo(Base, metaclass=Meta):
    @property
    def name(self):
        return "x"

    @staticmethod
    def open_repo(
        path,
        mode="r",
    ):
        return Repo()


@app.get("/health")
def health():
    return "ok"


if os.name == "nt":
    def windows_only():
        pass
""",
        [
            ("LIMIT_ROWS", "const", "LIMIT_ROWS = 50"),
            ("fetch_rows", "function", "async def fetch_rows"),
            ("Repo", "class", "class Repo"),
            ("name", "method", "def name"),
            ("open_repo", "method", "def open_repo"),
            ("health", "function", "def health"),
            ("GET /health", "route", "def health"),
            ("windows_only", "function", "def windows_only"),
        ],
        ["inner", "lower", "os"],
    ),
    "javascript": (
        "snip.js",
        """const fs = require('fs');

function plainFunction(a, b) {
  if (a) {
    return helperCall(b);
  }
  for (const x of b) { doThing(x); }
}

export default async function loadAll() {}
export function* walkTree(node) {}
const arrowFn = (a, b) => a + b;
export const asyncArrow = async (id) => {
  const inner = () => 1;
  return inner();
};
const single = x => x * 2;
let notAFunction = compute(1, 2);
export const API_BASE = '/api';
var legacy = function (x) { return x; };

class Store extends Base {
  static create(opts) {
    return new Store(opts);
  }
  get size() {
    return 1;
  }
  async save(record) {
    while (record) { record = next(record); }
  }
  #secret() {
    return 2;
  }
}

module.exports = {
  exportedMethod(a) {
    return a;
  },
  propFn: function (b) { return b; },
  arrowProp: (c) => c,
};

app.get('/users/:id', (req, res) => res.send('x'));
router.post("/users", createUser);
""",
        [
            ("plainFunction", "function", "function plainFunction"),
            ("loadAll", "function", "function loadAll"),
            ("walkTree", "function", "function* walkTree"),
            ("arrowFn", "function", "const arrowFn"),
            ("asyncArrow", "function", "const asyncArrow"),
            ("single", "function", "const single"),
            ("API_BASE", "const", "API_BASE ="),
            ("legacy", "function", "var legacy"),
            ("Store", "class", "class Store"),
            ("create", "method", "static create"),
            ("size", "method", "get size"),
            ("save", "method", "async save"),
            ("#secret", "method", "#secret()"),
            ("exportedMethod", "method", "exportedMethod(a)"),
            ("propFn", "method", "propFn:"),
            ("arrowProp", "method", "arrowProp:"),
            ("GET /users/:id", "route", "app.get"),
            ("POST /users", "route", "router.post"),
        ],
        [
            "if",
            "for",
            "while",
            "helperCall",
            "doThing",
            "notAFunction",
            "inner",
            "fs",
            "next",
            "compute",
        ],
    ),
    "typescript": (
        "snip.ts",
        """import type { Row } from './types';

export interface InvoiceRow extends Row {
  total(): number;
}

export type Money = { amount: number; currency: string };
type Maybe<T> = T | null;
export enum Status { Open, Paid }
declare function ambient(x: number): void;

export abstract class Billing<T> implements Service {
  private readonly rows: InvoiceRow[] = [];
  constructor(private api: Api) {}
  public async charge(id: string, amount: number): Promise<Money> {
    return this.api.charge(id, amount);
  }
  protected abstract refund(id: string): void;
  static of<U>(x: U): Billing<U> {
    return make(x);
  }
}

export const typedArrow = (a: number, b: number): number => a + b;
export function generic<T extends object>(value: T): T {
  return value;
}
""",
        [
            ("InvoiceRow", "type", "interface InvoiceRow"),
            ("Money", "type", "type Money"),
            ("Maybe", "type", "type Maybe"),
            ("Status", "type", "enum Status"),
            ("ambient", "function", "declare function"),
            ("Billing", "class", "class Billing"),
            ("charge", "method", "async charge"),
            ("of", "method", "static of"),
            ("typedArrow", "function", "const typedArrow"),
            ("generic", "function", "function generic"),
        ],
        ["constructor", "rows", "make", "return"],
    ),
    "vue": (
        "Basket.vue",
        """<template>
  <div @click="addItem(item)">{{ grandTotal }}</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const items = ref([]);
const grandTotal = computed(() => items.value.length);

function addItem(item) {
  items.value.push(item);
}

const removeItem = (id: number) => {
  items.value = items.value.filter((i) => i.id !== id);
};
</script>

<style scoped>
.a { color: red; }
</style>
""",
        [
            ("Basket", "component", "<template>"),
            ("grandTotal", "function", "const grandTotal"),
            ("addItem", "function", "function addItem"),
            ("removeItem", "function", "const removeItem"),
        ],
        ["items", "a", "color"],
    ),
    "php": (
        "snip.php",
        """<?php

namespace App\\Services;

use App\\Models\\User;

interface Billable
{
    public function bill(int $cents): bool;
}

trait LogsThings
{
    protected function logThing(string $m): void {}
}

enum Suit: string
{
    case Hearts = 'H';
}

abstract class PaymentService extends BaseService implements Billable
{
    use LogsThings;

    public const MAX_RETRIES = 3;
    private const string REGION = 'np';

    public function __construct(private Gateway $gateway)
    {
    }

    public function bill(int $cents): bool
    {
        if ($cents > 0) {
            return $this->gateway->charge($cents);
        }
        $fn = function ($x) { return $x; };
        return false;
    }

    abstract protected function refund(int $cents): void;

    public static function &byReference(array $a)
    {
        return $a;
    }
}

function top_level_helper($x)
{
    return strtoupper($x);
}

if (! function_exists('money')) {
    function money($cents)
    {
        return $cents / 100;
    }
}

$name = User::class;
""",
        [
            ("Billable", "type", "interface Billable"),
            ("LogsThings", "type", "trait LogsThings"),
            ("logThing", "method", "function logThing"),
            ("Suit", "type", "enum Suit"),
            ("PaymentService", "class", "class PaymentService"),
            ("MAX_RETRIES", "const", "MAX_RETRIES"),
            ("REGION", "const", "REGION"),
            ("__construct", "method", "__construct"),
            ("bill", "method", "public function bill(int $cents): bool\n"),
            ("refund", "method", "function refund"),
            ("byReference", "method", "byReference"),
            ("top_level_helper", "function", "function top_level_helper"),
            ("money", "function", "function money"),
        ],
        ["if", "fn", "strtoupper", "function_exists", "User", "charge", "name"],
    ),
    "laravel routes": (
        "routes/api.php",
        """<?php

use Illuminate\\Support\\Facades\\Route;

Route::get('/invoices', [InvoiceController::class, 'index']);
Route::post('/invoices', [InvoiceController::class, 'store'])->middleware('auth');
Route::middleware('auth:sanctum')->get('/user', function (Request $request) {
    return $request->user();
});
Route::apiResource('customers', CustomerController::class);
Route::prefix('admin')->group(function () {
    Route::delete('/users/{id}', [UserController::class, 'destroy']);
});
""",
        [
            ("GET /invoices", "route", "Route::get('/invoices'"),
            ("POST /invoices", "route", "Route::post"),
            ("GET /user", "route", "->get('/user'"),
            ("APIRESOURCE customers", "route", "apiResource"),
            ("DELETE /users/{id}", "route", "Route::delete"),
        ],
        ["group", "user", "prefix"],
    ),
    "go": (
        "snip.go",
        """package billing

import "net/http"

const MaxRetries = 3
var defaultTimeout = 5

type Invoice struct {
	ID    int
	Lines []Line
}

type (
	Line struct {
		Amount int
	}
	Totaler interface {
		Total() int
	}
)

func NewInvoice(id int) *Invoice {
	if id < 0 {
		return nil
	}
	return &Invoice{ID: id}
}

func (inv *Invoice) Total() int {
	total := 0
	for _, l := range inv.Lines {
		total += l.Amount
	}
	return total
}

func (Invoice) String() string { return "invoice" }

func Map[T any, U any](xs []T, f func(T) U) []U {
	return nil
}

func routes(mux *http.ServeMux) {
	mux.HandleFunc("/invoices", listInvoices)
}
""",
        [
            ("MaxRetries", "const", "const MaxRetries"),
            ("Invoice", "type", "type Invoice struct"),
            ("Line", "type", "Line struct"),
            ("Totaler", "type", "Totaler interface"),
            ("NewInvoice", "function", "func NewInvoice"),
            ("Total", "method", "func (inv *Invoice) Total"),
            ("String", "method", "String() string"),
            ("Map", "function", "func Map"),
            ("routes", "function", "func routes"),
            ("ANY /invoices", "route", "HandleFunc"),
        ],
        ["defaultTimeout", "ID", "Amount", "total", "listInvoices"],
    ),
    "rust": (
        "snip.rs",
        """use std::fmt;

pub const MAX_LINES: usize = 100;
static mut COUNTER: u32 = 0;

#[derive(Debug)]
pub struct Invoice<'a> {
    pub id: u32,
    label: &'a str,
}

pub enum Status {
    Open,
    Paid { at: u64 },
}

pub trait Totals {
    fn total(&self) -> u64;
    fn label(&self) -> String {
        String::from("x")
    }
}

impl<'a> Invoice<'a> {
    pub fn new(id: u32, label: &'a str) -> Self {
        let helper = |x: u32| x + 1;
        Invoice { id: helper(id), label }
    }

    pub(crate) async fn send(&self) -> Result<(), fmt::Error> {
        Ok(())
    }
}

impl<'a> Totals for Invoice<'a> {
    fn total(&self) -> u64 {
        if self.id > 0 { 1 } else { 0 }
    }
}

pub fn parse_line(input: &str) -> Option<char> {
    let c = '{';
    input.chars().find(|x| *x == c)
}

type Shared<T> = std::sync::Arc<T>;

macro_rules! invoice {
    ($id:expr) => { Invoice::new($id, "") };
}

mod tests {
    fn in_module() {}
}
""",
        [
            ("MAX_LINES", "const", "const MAX_LINES"),
            ("COUNTER", "const", "static mut COUNTER"),
            ("Invoice", "type", "pub struct Invoice"),
            ("Status", "type", "pub enum Status"),
            ("Totals", "type", "pub trait Totals"),
            ("label", "method", "fn label"),
            ("new", "method", "pub fn new"),
            ("send", "method", "async fn send"),
            ("parse_line", "function", "pub fn parse_line"),
            ("Shared", "type", "type Shared"),
            ("invoice", "macro", "macro_rules! invoice"),
            ("in_module", "function", "fn in_module"),
        ],
        ["helper", "Open", "Paid", "id", "find", "c"],
    ),
    "ruby": (
        "snip.rb",
        """require 'json'

module Billing
  MAX_LINES = 100

  class Invoice < Base
    attr_reader :lines

    def initialize(customer)
      @customer = customer
    end

    def total
      lines.sum(&:amount)
    end

    def paid?
      true
    end

    def self.find_by_number(number)
      new(nil)
    end
  end

  def self.setup!
  end
end

def top_level(x)
  x.each do |y|
    puts y
  end
end
""",
        [
            ("Billing", "type", "module Billing"),
            ("MAX_LINES", "const", "MAX_LINES = 100"),
            ("Invoice", "class", "class Invoice"),
            ("initialize", "method", "def initialize"),
            ("total", "method", "def total"),
            ("paid?", "method", "def paid?"),
            ("find_by_number", "method", "def self.find_by_number"),
            ("setup!", "method", "def self.setup!"),
            ("top_level", "function", "def top_level"),
        ],
        ["lines", "puts", "each", "attr_reader"],
    ),
    "java": (
        "Snip.java",
        """package com.shop.billing;

import java.util.List;

@Service
public class InvoiceService extends BaseService implements Billable {
    private static final int MAX = 3;
    private final List<Invoice> cache = new ArrayList<>();

    public InvoiceService(Repo repo) {
        super(repo);
    }

    @Override
    public Money total(List<Line> lines) throws BillingException {
        if (lines.isEmpty()) {
            return Money.zero();
        }
        for (Line l : lines) { add(l); }
        return compute(lines);
    }

    protected abstract void refund(String id);

    static <T> List<T> wrap(T item) {
        return List.of(item);
    }

    @GetMapping("/invoices/{id}")
    public Invoice show(@PathVariable String id) {
        return repo.find(id);
    }

    private enum State { OPEN, PAID }

    interface Visitor {
        void visit(Invoice invoice);
    }
}

record Line(String label, int amount) {}
""",
        [
            ("InvoiceService", "class", "public class InvoiceService"),
            ("InvoiceService", "method", "public InvoiceService(Repo repo)"),
            ("total", "method", "public Money total"),
            ("refund", "method", "abstract void refund"),
            ("wrap", "method", "wrap(T item)"),
            ("show", "method", "public Invoice show"),
            ("GET /invoices/{id}", "route", "@GetMapping"),
            ("State", "type", "enum State"),
            ("Visitor", "type", "interface Visitor"),
            ("visit", "method", "void visit"),
            ("Line", "class", "record Line"),
        ],
        [
            "if",
            "for",
            "add",
            "compute",
            "cache",
            "MAX",
            "zero",
            "find",
            "of",
            "super",
            "ArrayList",
        ],
    ),
    "kotlin": (
        "snip.kt",
        """package shop

const val MAX_LINES = 100
typealias Lines = List<Line>

data class Line(val label: String, val amount: Int)

interface Totals {
    fun total(): Int
}

sealed class Invoice(
    val id: Int,
    val lines: Lines,
) : Totals {
    override fun total(): Int {
        if (lines.isEmpty()) return 0
        return lines.sumOf { it.amount }
    }

    companion object {
        fun empty(): Invoice = Draft(0)
    }
}

object Registry {
    fun register(invoice: Invoice) {}
}

fun topLevel(x: Int): Int = x + 1
suspend fun <T> List<T>.firstPaid(): T? = null
""",
        [
            ("MAX_LINES", "const", "const val"),
            ("Lines", "type", "typealias"),
            ("Line", "class", "data class Line"),
            ("Totals", "type", "interface Totals"),
            ("total", "method", "fun total(): Int\n"),
            ("Invoice", "class", "sealed class Invoice"),
            ("total", "method", "override fun total"),
            ("empty", "method", "fun empty"),
            ("Registry", "class", "object Registry"),
            ("register", "method", "fun register"),
            ("topLevel", "function", "fun topLevel"),
            ("firstPaid", "function", "firstPaid"),
        ],
        ["if", "sumOf", "Draft", "isEmpty"],
    ),
    "c": (
        "snip.c",
        """#include <stdio.h>
#include "snip.h"

#define MAX_LINES 100
#define SQUARE(x) ((x) * (x))

struct invoice {
    int id;
    int lines[MAX_LINES];
};

typedef struct {
    int amount;
} line_t;

typedef int (*visitor_fn)(struct invoice *);
enum status { OPEN, PAID };

static int helper(int x);

static int helper(int x)
{
    if (x > 0) {
        return SQUARE(x);
    }
    return printf("%d {\\n", x);
}

struct invoice *invoice_new(int id) {
    struct invoice *inv = malloc(sizeof(*inv));
    inv->id = helper(id);
    return inv;
}

int main(int argc, char **argv)
{
    for (int i = 0; i < argc; i++) { helper(i); }
    return 0;
}
""",
        [
            ("MAX_LINES", "macro", "#define MAX_LINES"),
            ("SQUARE", "macro", "#define SQUARE"),
            ("invoice", "type", "struct invoice {"),
            ("line_t", "type", "} line_t;"),
            ("visitor_fn", "type", "visitor_fn"),
            ("status", "type", "enum status"),
            ("helper", "function", "static int helper(int x)\n"),
            ("invoice_new", "function", "invoice_new(int id)"),
            ("main", "function", "int main"),
        ],
        ["if", "for", "printf", "malloc", "inv", "sizeof", "id"],
    ),
    "c header": (
        "snip.h",
        """#ifndef SNIP_H
#define SNIP_H

#define SNIP_VERSION "1.2"

struct invoice;
int invoice_total(const struct invoice *inv);
struct invoice *invoice_new(int id);
extern int invoice_count;

#endif
""",
        [
            ("SNIP_VERSION", "macro", "#define SNIP_VERSION"),
            ("invoice_total", "function", "int invoice_total"),
            ("invoice_new", "function", "invoice_new(int id)"),
        ],
        ["SNIP_H", "invoice_count"],
    ),
    "c++": (
        "snip.cpp",
        """#include <string>

namespace billing {

class Invoice : public Totals {
public:
    Invoice(int id);
    ~Invoice();
    int total() const override;
    static Invoice parse(const std::string &text);
private:
    int id_ = 0;
};

Invoice::Invoice(int id) : id_(id) {}

int Invoice::total() const
{
    if (id_ > 0) {
        return compute(id_);
    }
    return 0;
}

template <typename T>
T clamp_value(T value, T low, T high) {
    return value < low ? low : value;
}

using InvoiceList = std::vector<Invoice>;

}  // namespace billing
""",
        [
            ("Invoice", "class", "class Invoice"),
            ("total", "method", "int total() const override;"),
            ("parse", "method", "static Invoice parse"),
            ("Invoice", "method", "Invoice::Invoice(int id)"),
            ("total", "method", "int Invoice::total() const"),
            ("clamp_value", "function", "T clamp_value"),
            ("InvoiceList", "type", "using InvoiceList"),
        ],
        ["if", "compute", "id_", "billing", "return"],
    ),
    "shell": (
        "snip.sh",
        """#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage"
}

function deploy_app {
  local target="$1"
  rsync -a . "$target"
}

function check-health() { curl -fsS "$1"; }

retry()
{
  "$@" || "$@"
}

main() { usage; deploy_app "$1"; }
main "$@"
""",
        [
            ("usage", "function", "usage() {"),
            ("deploy_app", "function", "function deploy_app"),
            ("check-health", "function", "function check-health"),
            ("retry", "function", "retry()"),
            ("main", "function", "main() {"),
        ],
        ["echo", "local", "rsync", "curl", "set"],
    ),
    "a script with no extension": (
        "tool",
        '''#!/usr/bin/env python3
"""A tool."""


def run_tool(argv):
    return 0
''',
        [("run_tool", "function", "def run_tool")],
        [],
    ),
}


def languages(tmp):
    d = os.path.join(tmp, "snips")
    os.makedirs(d)
    write(d, {name: text for name, text, _, _ in SNIPPETS.values()})
    write(
        d,
        {
            "notes.txt": "def not_source():\n",
            "data.json": '{"function": "nope"}\n',
            "plain": "def no_shebang():\n    pass\n",
        },
    )
    data = mapped(d, env_for(tmp))
    out = {}
    for lang, (name, text, want, never) in SNIPPETS.items():
        got = {}
        for f in data["files"]:
            if f["path"] == name:
                for s in f["symbols"]:
                    got.setdefault(s["name"], []).append((s["kind"], s["line"]))
        missing = [
            f"{n} ({k}, line {line_of(text, needle)})"
            for n, k, needle in want
            if (k, line_of(text, needle)) not in got.get(n, [])
        ]
        extra = [n for n in never if n in got]
        if missing or extra:
            print(
                f"  {lang}: missing {missing}, shouldn't be there {extra}; got {sorted(got.items())}"
            )
        out[
            f"{lang}: {len(want)} definitions on their lines, {len(never)} look-alikes left out"
        ] = not missing and not extra
    paths = {f["path"] for f in data["files"]}
    out["a .txt, a .json and a file with no shebang aren't source"] = not paths & {
        "notes.txt",
        "data.json",
        "plain",
    }
    out["--json says what read them: ast for Python, patterns for the rest"] = (
        data.get("source", {}).get("python") == "ast"
        and data["source"].get("others") == "patterns"
    )
    return out


def ctags(tmp):
    program = shutil.which("universal-ctags") or shutil.which("ctags")
    version = run([program, "--version"]).stdout if program else ""
    if (
        "Universal Ctags" not in version
        or "json" not in run([program, "--list-features"]).stdout
    ):
        return {"universal-ctags as a better source (not installed here)": SKIP}
    d = os.path.join(tmp, "snips")
    os.makedirs(d)
    write(d, {name: text for name, text, _, _ in SNIPPETS.values()})
    env = env_for(tmp, SAKURA_MAP_SOURCE="")
    data = mapped(d, env)
    out = {}
    by_file = {f["path"]: f for f in data["files"]}
    for lang in (
        "javascript",
        "php",
        "go",
        "rust",
        "ruby",
        "java",
        "c",
        "shell",
        "laravel routes",
    ):
        name, text, want, never = SNIPPETS[lang]
        got = {}
        for s in by_file.get(name, {}).get("symbols", []):
            got.setdefault(s["name"], []).append(s["line"])
        missing = [
            n for n, k, needle in want if line_of(text, needle) not in got.get(n, [])
        ]
        extra = [n for n in never if n in got]
        if missing or extra:
            print(
                f"  ctags {lang}: missing {missing}, shouldn't be there {extra}; got {sorted(got.items())}"
            )
        out[
            f"with ctags, {lang}: the same definitions on the same lines, the same look-alikes left out"
        ] = not missing and not extra
    builtin = mapped(d, env, "--source", "builtin")
    tools = run([MAP, "--tools"], env).stdout
    out["--json says ctags read them, and Python is still ast"] = (
        "Universal Ctags" in data["source"]["others"]
        and data["source"]["python"] == "ast"
        and by_file["snip.go"]["source"] == "patterns + ctags"
        and by_file["snip.py"]["source"] == "ast"
    )
    out["--source builtin turns it off, and the cache isn't shared between the two"] = (
        builtin["source"]["others"] == "patterns"
        and {f["path"]: f["source"] for f in builtin["files"]}["snip.go"] == "patterns"
    )
    out["--tools names the ctags it found"] = (
        "Universal Ctags" in tools and program in tools
    )
    return out


def hook(tmp):
    d = project(os.path.join(tmp, "shopkit"))
    env = env_for(tmp)
    flag = os.path.join(env["SAKURA_HOME"], "map")

    def fire(prompt, cwd=d, session="s1", event="UserPromptSubmit"):
        r = run(
            [sys.executable, HOOK],
            env,
            stdin=json.dumps(
                {
                    "hook_event_name": event,
                    "prompt": prompt,
                    "cwd": cwd,
                    "session_id": session,
                }
            ),
        )
        if not r.stdout.strip():
            return ""
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    task = "fix the rounding bug in invoice.py, total() is off by a paisa"
    off = fire(task)
    before = os.path.exists(flag)
    on = run([MAP, "on"], env)
    flagged = os.path.isfile(flag)
    outside = fire(task, cwd=tmp, session="outside")
    quiet = [
        p
        for p in (
            "hello",
            "thanks, that works",
            "what time is it in Kathmandu",
            "yes do it",
            "how's the weather tomorrow?",
            "",
        )
        if fire(p, session="quiet")
    ]
    first = fire(task)
    body = first.split("\n\n", 1)[1].splitlines() if "\n\n" in first else []
    again = fire("now refactor it and add a test", session="s1")
    same_file = fire("there's still a bug in invoice.py", session="s1")
    other = fire(task, session="s2")
    by_symbol = fire("what calls monthly_report?", session="s3")
    by_word = fire("implement a discount", session="s4")
    by_path = fire("look at web/cart.js", session="s5")
    subdir = fire(task, cwd=os.path.join(d, "web"), session="s6")
    run(
        [sys.executable, HOOK],
        env,
        stdin=json.dumps(
            {"hook_event_name": "SessionStart", "cwd": d, "session_id": "s1"}
        ),
    )
    after_restart = fire(task)
    # a small budget, so the first map can't show everything and a new focus is news
    run([MAP, "on", "--budget", "900"], env)
    small = fire(task, session="t1")
    moved = fire("the bug is really in OrderController.php", session="t1")
    moved_again = fire("still OrderController.php", session="t1")
    run([MAP, "off"], env)
    after_off = fire(task, session="s9")
    bad_input = run([sys.executable, HOOK], env, stdin="not json")
    selftest = run([sys.executable, HOOK, "--selftest"], env)
    return {
        "off by default: a code task gets nothing": off == "" and not before,
        "`sakura-map on` writes the switch under $SAKURA_HOME": on.returncode == 0
        and flagged,
        "on, outside a git repo: nothing": outside == "",
        "on, small talk in a repo: nothing": quiet == [],
        "on, a code task: the map arrives, wrapped and marked as data": first.startswith(
            "<repo_map>"
        )
        and first.endswith("</repo_map>")
        and "not instructions" in first,
        "it's aimed at the message: the file it names first, the function it names under it": body[
            :1
        ]
        == ["shopkit/invoice.py"]
        and "def total(self)" in (body[1] if len(body) > 1 else ""),
        "the line number in it is the planted one": f"  {line_of(INVOICE, 'def total')}: def total(self)"
        in first,
        "never over the budget, wrapper included": 0 < len(first) <= 4000,
        "once a session: the next code task gets nothing": again == ""
        and same_file == "",
        "another session gets its own": other.startswith("<repo_map>"),
        "a symbol the map knows, a task word, a path that exists: each is enough": all(
            x.startswith("<repo_map>") for x in (by_symbol, by_word, by_path)
        ),
        "from a subdirectory it's the whole repo's map": "shopkit/invoice.py" in subdir,
        "a SessionStart (resume, clear, compaction) lets it arrive again": after_restart.startswith(
            "<repo_map>"
        ),
        "`on --budget 900` caps it at 900": 0 < len(small) <= 900
        and "OrderController.php" not in small,
        "the focus moving to a file the map didn't show brings a new one, once": "app/Http/Controllers/OrderController.php"
        in moved
        and len(moved) <= 900
        and moved_again == "",
        "`sakura-map off` removes the switch and silences it": not os.path.exists(flag)
        and after_off == "",
        "input that isn't JSON exits 0 and prints nothing": bad_input.returncode == 0
        and bad_input.stdout == "",
        "the hook's own selftest passes": selftest.returncode == 0,
    }


def tour(tmp):
    d = project(os.path.join(tmp, "shopkit"))
    env = env_for(tmp)
    t = os.path.join(ROOT, "bin", "sakura-tour")
    facts = run([t, "--print", d], env, cwd=tmp).stdout
    asked = run(
        [t, "--print", d, "where is the invoice total computed?"], env, cwd=tmp
    ).stdout
    at = asked.find("The map (sakura-map")
    stub = os.path.join(tmp, "stubbin")
    os.makedirs(stub)
    shutil.copy(
        t, os.path.join(stub, "sakura-tour")
    )  # a copy with no sakura-map beside it
    without = run(
        [sys.executable, os.path.join(stub, "sakura-tour"), "--print", d], env, cwd=tmp
    )
    return {
        "the tour's facts include the map, with a planted line number": "The map (sakura-map"
        in facts
        and "shopkit/money.py" in facts
        and f"  {line_of(MONEY, 'def format_money')}: def format_money(amount, currency=DEFAULT_CURRENCY)"
        in facts,
        "a question aims the map": at >= 0
        and asked[at:].splitlines()[2:3] == ["shopkit/invoice.py"],
        "the facts it gathered before are all still there": all(
            x in facts
            for x in (
                "Repository:",
                "Languages: ",
                "Git: 1 commits",
                "--- README.md (first lines) ---",
            )
        ),
        "the map stays small inside the brief (1,500 characters)": 0
        < len(facts[facts.find("The map (sakura-map") : facts.find("--- README.md")])
        < 1700,
        "without sakura-map the tour still gathers its facts": without.returncode == 0
        and "Repository:" in without.stdout
        and "The map" not in without.stdout,
    }


CASES = {
    "rank": rank,
    "lines": lines,
    "aim": aim,
    "budget": budget,
    "ignored": ignored,
    "broken": broken,
    "cache": cache,
    "big": big,
    "languages": languages,
    "ctags": ctags,
    "hook": hook,
    "tour": tour,
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
    print(f"\n{passed}/{total}" + (f" ({skipped} skipped)" if skipped else ""))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
