#!/usr/bin/env python3
"""Hackathon demo: the pubskill MCP vertical slice.

Walks the Amazon-submission story through the real MCP Streamable HTTP surface:

  1. pubskill_identity         — who is serving, and from which pinned source
  2. pubskill_list_skills      — the full 44-skill canonical catalog
  3. pubskill_resolve_skills   — which skills apply, scored and non-authoritative
  4. pubskill_collect_metadata — schema-2 MSDMD over a public repo, exact revision
  5. pubskill_query_metadata   — read-only filtering over the collection
  6. pubskill_get_skill        — retrieve the selected canonical skill
  7. pubskill_get_resource     — retrieve one skill resource byte-exactly

Usage:
    PORT=8080 python service.py          # terminal 1
    python tools/hackathon_demo.py       # terminal 2

Standard library only; no Alexa+ or MCP SDK required. Use --interactive to
step through each section for a screen recording, --delay to control pacing,
and --no-collect to run the demo without network access.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8080/mcp"
DEFAULT_REPO_URL = "https://github.com/octocat/Hello-World"
DEFAULT_REVISION = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"


def rpc(url: str, request_id: int, method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def tool_call(url: str, request_id: int, name: str, arguments: dict) -> dict:
    response = rpc(url, request_id, "tools/call", {"name": name, "arguments": arguments})
    result = response.get("result", {})
    if result.get("isError"):
        raise RuntimeError(f"{name} failed: {result.get('content', [{}])[0].get('text', '')[:400]}")
    text = result.get("content", [{}])[0].get("text", "{}")
    return json.loads(text)


def section(number: int, title: str) -> None:
    print(f"\n=== Step {number} — {title} ===", flush=True)


def show(label: str, value: object) -> None:
    print(f"{label}: {value}", flush=True)


def excerpt(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def pause(delay: float, interactive: bool) -> None:
    if interactive:
        input("Press Enter for the next step…")
    elif delay > 0:
        time.sleep(delay)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="MCP endpoint URL")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="public repository for the collect step")
    parser.add_argument("--revision", default=DEFAULT_REVISION, help="exact revision for the collect step")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between steps")
    parser.add_argument("--interactive", action="store_true", help="wait for Enter between steps")
    parser.add_argument("--no-collect", action="store_true", help="skip the network collection/query steps")
    args = parser.parse_args(argv)

    try:
        initialized = rpc(args.url, 1, "initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "pubskill-hackathon-demo", "version": "1.0"},
        })
        server = initialized["result"]["serverInfo"]
        print(f"pubskill MCP demo — {server['name']} {server['version']} "
              f"(MCP {initialized['result']['protocolVersion']})", flush=True)
        rpc(args.url, 2, "notifications/initialized")

        request_id = 10
        section(1, "pubskill_identity — who is serving")
        identity = tool_call(args.url, request_id, "pubskill_identity", {}); request_id += 1
        show("producer", f"{identity['identity']['producer']['repository']}@{identity['identity']['producer']['commit'][:12]}")
        show("consumer", f"{identity['identity']['consumer']['repository']}@{identity['identity']['consumer']['commit'][:12]}")
        show("catalog digest", identity["identity"]["catalog"]["catalog_digest"][:16] + "…")
        pause(args.delay, args.interactive)

        section(2, "pubskill_list_skills — the canonical catalog")
        skills = tool_call(args.url, request_id, "pubskill_list_skills", {}); request_id += 1
        show("skill_count", skills["skill_count"])
        show("first skills", ", ".join(item["name"] for item in skills["skills"][:6]) + ", …")
        pause(args.delay, args.interactive)

        section(3, "pubskill_resolve_skills — candidates, not authority")
        resolved = tool_call(args.url, request_id, "pubskill_resolve_skills",
                             {"query": "collect repository metadata without executing code"}); request_id += 1
        show("method", resolved["method"])
        show("authoritative", resolved["authoritative"])
        for item in resolved["candidates"][:3]:
            show("candidate", f"{item['name']} (score {item['score']})")
        pause(args.delay, args.interactive)

        collection = None
        if not args.no_collect:
            section(4, "pubskill_collect_metadata — schema-2 MSDMD over a public repo")
            show("repo_url", args.repo_url)
            show("revision", args.revision)
            collected = tool_call(args.url, request_id, "pubskill_collect_metadata",
                                  {"repo_url": args.repo_url, "revision": args.revision}); request_id += 1
            receipt = collected["receipt"]["repository"]
            show("resolved_commit", receipt["resolved_commit"])
            show("exact_revision_match", receipt["resolved_commit"] == args.revision)
            collection = collected["collection"]
            show("collection_schema", f"{collection['schema']} {collection['schema_version']}")
            show("facts", len(collection.get("facts", [])))
            show("reader_runs", len(collection.get("reader_runs", [])))
            show("diagnostics", len(collection.get("diagnostics", [])))
            pause(args.delay, args.interactive)

            section(5, "pubskill_query_metadata — read-only filtering")
            queried = tool_call(args.url, request_id, "pubskill_query_metadata",
                                {"collection": collection, "diagnostics_only": True}); request_id += 1
            show("matched_diagnostics", queried["counts"]["matched_diagnostics"])
            show("total_diagnostics", queried["counts"]["total_diagnostics"])
            show("coverage", json.dumps(queried.get("coverage", {}), sort_keys=True)[:200])
            pause(args.delay, args.interactive)

        section(6, "pubskill_get_skill — retrieve the selected canonical skill")
        skill = tool_call(args.url, request_id, "pubskill_get_skill", {"name": "msdmd"}); request_id += 1
        show("name", skill["skill"]["name"])
        show("kind", skill["skill"]["kind"])
        show("status", skill["skill"]["status"])
        show("description", excerpt(skill["skill"]["description"] or ""))
        show("resources", len(skill["skill"]["resources"]))
        pause(args.delay, args.interactive)

        section(7, "pubskill_get_resource — one resource byte-exactly")
        resource = tool_call(args.url, request_id, "pubskill_get_resource",
                             {"name": "msdmd", "path": "parsers/universal.py"}); request_id += 1
        show("path", resource["resource"]["path"])
        show("digest", resource["resource"]["digest"][:16] + "…")
        show("content", excerpt(resource["resource"]["content_utf8"], 180))
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode()[:400]}", file=sys.stderr)
        print("Is the service running? Start it with:  PORT=8080 python service.py", file=sys.stderr)
        return 2
    except urllib.error.URLError as error:
        print(f"Could not reach {args.url}: {error.reason}", file=sys.stderr)
        print("Is the service running? Start it with:  PORT=8080 python service.py", file=sys.stderr)
        return 2

    print("\nDemo complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
