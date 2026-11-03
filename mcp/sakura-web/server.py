#!/usr/bin/env python3
"""sakura-web — MCP server exposing the webkit tools over newline-delimited JSON-RPC 2.0 (stdio).

Zero dependencies (stdlib only). stdout carries protocol frames; all logging goes to stderr.
The same tools are also available as shell CLIs (web_search / fetch_url / wikipedia) for models
that drive the shell rather than MCP.
"""
import json
import sys

import webkit
from webkit import log

PROTO_DEFAULT = "2025-06-18"
DISPATCH = {"web_search": webkit.web_search, "fetch_url": webkit.fetch_url, "wikipedia": webkit.wikipedia}
EMPTY_LIST = {
    "resources/list": "resources",
    "resources/templates/list": "resourceTemplates",
    "prompts/list": "prompts",
}


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        proto = (req.get("params") or {}).get("protocolVersion") or PROTO_DEFAULT
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": proto,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sakura-web", "version": "1.0.0"},
            },
        }
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": webkit.TOOLS}}
    if method in EMPTY_LIST:
        return {"jsonrpc": "2.0", "id": rid, "result": {EMPTY_LIST[method]: []}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        fn = DISPATCH.get(name)
        if not fn:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown tool {name}"}}
        try:
            text = fn(**(params.get("arguments") or {}))
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            log("tool error:", name, repr(e))
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": f"Error running {name}: {e}"}], "isError": True},
            }
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main():
    log("up; stdio JSON-RPC")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            log("bad json:", repr(e))
            continue
        for one in (req if isinstance(req, list) else [req]):
            resp = handle(one)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
