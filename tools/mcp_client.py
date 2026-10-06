#!/usr/bin/env python3
"""Minimal MCP Streamable HTTP client for demonstrating pubskill.

Usage:
    python tools/mcp_client.py --url http://127.0.0.1:8080/mcp

Runs an initialize -> tools/list -> tool-call sequence against a running
pubskill service and prints the JSON-RPC responses. Standard library only; no
Alexa+ or MCP SDK required.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def rpc(url: str, request_id: int, method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/mcp")
    args = parser.parse_args(argv)

    def show(label: str, response: dict) -> None:
        print(f"--- {label} ---")
        print(json.dumps(response, indent=2, ensure_ascii=False)[:1200])

    try:
        initialized = rpc(args.url, 1, "initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "pubskill-local-client", "version": "0.1.0"},
        })
        show("initialize", initialized)
        rpc(args.url, 2, "notifications/initialized")

        tools = rpc(args.url, 3, "tools/list")
        show("tools/list", tools)

        calls = [
            ("pubskill_identity", {}),
            ("pubskill_list_skills", {}),
            ("pubskill_get_skill", {"name": "msdmd"}),
            ("pubskill_get_resource", {"name": "msdmd", "path": "parsers/universal.py"}),
            ("pubskill_resolve_skills", {"query": "metadata collection"}),
        ]
        for request_id, (name, arguments) in enumerate(calls, start=4):
            response = rpc(args.url, request_id, "tools/call", {"name": name, "arguments": arguments})
            text = response.get("result", {}).get("content", [{}])[0].get("text", "")
            summary = text[:400] if response.get("result", {}).get("isError") is False else text
            print(f"--- tools/call {name} ---")
            print(json.dumps(response.get("result", {}).get("isError", True), indent=0))
            print(summary)
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode()[:500]}", file=sys.stderr)
        return 2
    except urllib.error.URLError as error:
        print(f"could not reach {args.url}: {error.reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
