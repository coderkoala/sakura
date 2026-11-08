#!/usr/bin/env python3
"""Does the torrent helper behave without a daemon, a network, or transmission installed? Deterministic checks:
--help prints usage and exits 0, a bare `add` exits 2 with a usage line, a magnet's dn= is parsed, ensure() names
the apt command when transmission is off PATH, and the daemon flags builder only emits flags its --help lists.

  evals/torrent.py
"""
import importlib.machinery
import os
import subprocess
import sys
import tempfile

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "torrent")


def run(args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, TOOL, *args], env=e, capture_output=True, text=True, timeout=60)


def load():
    return importlib.machinery.SourceFileLoader("torrent_tool", TOOL).load_module()


def help_case(tmp):
    r = run(["--help"])
    return {"--help exits 0": r.returncode == 0,
            "it prints the usage": "torrent add" in r.stdout and "torrent watch" in r.stdout and "torrent rm" in r.stdout}


def add_no_args(tmp):
    r = run(["add"])
    return {"a bare add exits 2": r.returncode == 2,
            "with a usage line": "usage: torrent add" in r.stderr}


def magnet_dn(tmp):
    t = load()
    plus = t.magnet_name("magnet:?xt=urn:btih:c9e15763f722f23e98a29decdfae341b98d53056&dn=Debian+12.5+netinst&tr=udp%3A%2F%2Fexample")
    pct = t.magnet_name("magnet:?dn=cosmos%20laundromat&xt=urn:btih:abc")
    return {"a + encoded dn is parsed": plus == "Debian 12.5 netinst",
            "a %20 encoded dn is parsed": pct == "cosmos laundromat",
            "a magnet without dn gives None": t.magnet_name("magnet:?xt=urn:btih:abc") is None,
            "a non-magnet gives None": t.magnet_name("/tmp/a.torrent") is None}


def ensure_missing(tmp):
    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir)
    os.symlink(sys.executable, os.path.join(bindir, os.path.basename(sys.executable)))
    r = run(["list"], env={"PATH": bindir})
    return {"ensure() exits 1 without transmission": r.returncode == 1,
            "and names the install command": "sudo -A apt-get install -y transmission-cli transmission-daemon" in r.stderr,
            "it does not try to install": "apt-get" not in r.stdout}


def flags_builder(tmp):
    t = load()
    with_portmap = """Usage: transmission-daemon [options]
 -g  --config-dir <path>       Where to look for configuration files
 -w  --download-dir <path>     Where to save downloaded data
 -a  --allowed <list>          Allowed IP addresses
 -T  --no-auth                 Don't require authentication
 -i  --rpc-bind-address <ip>   Where to listen for RPC connections
 -p  --port <port>             RPC port
 -P  --no-portmap              Disable portmapping
 -peerport --no-dht-legacy     (a near miss, not --no-dht)
"""
    without = """Usage: transmission-daemon [options]
 -g  --config-dir <path>       Where to look for configuration files
 -w  --download-dir <path>     Where to save downloaded data
 -p  --port <port>             RPC port
"""
    a = t.daemon_flags(with_portmap, "/c", "/d")
    b = t.daemon_flags(without, "/c", "/d")
    known = {f for line in with_portmap.splitlines() for f in line.split() if f.startswith("--")}
    return {"--no-portmap passed when listed": "--no-portmap" in a,
            "--no-portmap withheld when absent": "--no-portmap" not in b and "--no-auth" not in b,
            "--no-dht-legacy does not count as --no-dht": "--no-dht" not in a,
            "config dir rides its flag": a[a.index("--config-dir") + 1] == "/c",
            "download dir rides its flag": a[a.index("--download-dir") + 1] == "/d",
            "RPC stays on localhost": a[a.index("--rpc-bind-address") + 1] == "127.0.0.1" and a[a.index("--port") + 1] == "9096",
            "every emitted flag is a listed one": all(f in known for f in a if f.startswith("--")),
            "the sparse help still gets its dirs and port": b[b.index("--config-dir") + 1] == "/c" and "--port" in b}


CASES = {"help": help_case, "add-no-args": add_no_args, "magnet-dn": magnet_dn,
         "ensure-missing": ensure_missing, "flags-builder": flags_builder}


def main():
    passed = total = 0
    for name, case in CASES.items():
        with tempfile.TemporaryDirectory() as tmp:
            print(f"\n== {name}", flush=True)
            try:
                results = case(tmp)
            except Exception as e:
                results = {f"ran without crashing ({e})": False}
            for check, ok in results.items():
                print(f"  {'ok  ' if ok else 'FAIL'} {check}", flush=True)
                total += 1
                passed += bool(ok)
    print(f"\ntorrent: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
