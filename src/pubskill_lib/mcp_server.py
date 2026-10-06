"""MCP Streamable HTTP transport (specification 2025-11-25) for pubskill.

The transport is stateless JSON-over-HTTP. All tools call the same
`pubskill_lib.api` application functions used by the HTTP API; the MCP adapter
maintains no second catalog and performs no collection of its own.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from . import __version__, api
from .acquisition import AcquisitionError
from .collections import CollectionError

PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "pubskill-lib"

JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603

TOOLS: list[dict[str, Any]] = [
    {
        "name": "pubskill_identity",
        "description": "Return the pinned producer/consumer/catalog identities and reader runtime status of this pubskill service.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "pubskill_list_skills",
        "description": "List the complete propagated skill catalog (44 skills) with names, descriptions, kinds, statuses, source commits and byte digests.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "pubskill_get_skill",
        "description": "Retrieve one canonical skill's SKILL.md text and its listed resources.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pubskill_get_resource",
        "description": "Retrieve one non-SKILL.md resource inside a canonical skill directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
            },
            "required": ["name", "path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pubskill_collect_metadata",
        "description": "Clone one allowed public HTTPS repository at an exact revision and collect native-first schema-2 MSDMD metadata without executing target code. Returns the resolved immutable commit, the collection, and a bounded acquisition receipt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_url": {"type": "string", "minLength": 1},
                "revision": {"type": "string"},
                "require_sources": {"type": "array", "items": {"type": "string"}},
                "require_facts": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["repo_url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pubskill_query_metadata",
        "description": "Read-only filtering over a supplied schema-2 MSDMD collection (or over a freshly collected repository when repo_url is supplied).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "collection": {"type": "object"},
                "repo_url": {"type": "string"},
                "revision": {"type": "string"},
                "convention": {"type": "string"},
                "fact_kind": {"type": "string"},
                "standing": {"type": "string"},
                "subject_contains": {"type": "string"},
                "path_glob": {"type": "string"},
                "diagnostic_status": {"type": "string"},
                "diagnostics_only": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "pubskill_resolve_skills",
        "description": "Rank canonical skills by keyword overlap over a supplied query. Returns scored candidates with the ranking method; never declares one skill authoritative.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in TOOLS
    ]


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _jsonrpc_result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _tool_content(text: str, *, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def call_tool(name: str, arguments: dict) -> dict:
    """Execute one pubskill MCP tool against the shared application layer."""
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be a JSON object")
    tool_names = {tool["name"] for tool in TOOLS}
    if name not in tool_names:
        raise ValueError(f"unknown tool: {name}")

    if name == "pubskill_identity":
        result = api.v1_identity()
    elif name == "pubskill_list_skills":
        result = api.v1_list_skills()
    elif name == "pubskill_get_skill":
        result = api.v1_get_skill(arguments["name"])
    elif name == "pubskill_get_resource":
        result = api.v1_get_resource(arguments["name"], arguments["path"])
    elif name == "pubskill_collect_metadata":
        result = api.v1_collect(
            arguments["repo_url"],
            revision=arguments.get("revision"),
            require_sources=tuple(arguments.get("require_sources") or ()),
            require_facts=tuple(arguments.get("require_facts") or ()),
        )
    elif name == "pubskill_query_metadata":
        result = api.v1_query(
            collection=arguments.get("collection"),
            repo_url=arguments.get("repo_url"),
            revision=arguments.get("revision"),
            convention=arguments.get("convention"),
            fact_kind=arguments.get("fact_kind"),
            standing=arguments.get("standing"),
            subject_contains=arguments.get("subject_contains"),
            path_glob=arguments.get("path_glob"),
            diagnostic_status=arguments.get("diagnostic_status"),
            diagnostics_only=bool(arguments.get("diagnostics_only", False)),
            limit=int(arguments.get("limit", 200)),
        )
    elif name == "pubskill_resolve_skills":
        result = api.v1_resolve(
            arguments["query"],
            limit=arguments.get("limit", 10),
        )
    else:  # pragma: no cover - guarded above
        raise ValueError(f"unknown tool: {name}")
    return _tool_content(json.dumps(result, ensure_ascii=False))


def handle_jsonrpc(payload: dict) -> dict | None:
    """Dispatch one JSON-RPC request; returns None for notifications."""
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        raise ValueError("invalid JSON-RPC envelope")
    method = payload.get("method")
    if not isinstance(method, str):
        raise ValueError("missing JSON-RPC method")
    request_id = payload.get("id")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    if method == "initialize":
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
                "instructions": (
                    "pubskill exposes the pinned skill-lib catalog and schema-2 "
                    "MSDMD collection/query as MCP tools. Schema-1 /inspect "
                    "remains a separate HTTP contract."
                ),
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _jsonrpc_result(request_id, {})
    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": tool_schemas()})
    if method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            raise ValueError("tools/call requires a tool name")
        try:
            return _jsonrpc_result(request_id, call_tool(params["name"], params.get("arguments", {})))
        except (KeyError, ValueError, AcquisitionError, CollectionError) as error:
            return _jsonrpc_result(
                request_id,
                _tool_content(str(error) or "invalid tool arguments", is_error=True),
            )
    return _jsonrpc_error(request_id, JSONRPC_METHOD_NOT_FOUND, f"method not found: {method}")


def handle_http_bytes(body: bytes, accept_header: str = "") -> tuple[int, str, bytes]:
    """Handle one MCP Streamable HTTP request body.

    Returns (status, content_type, response_body). The transport is stateless;
    the server assigns no session id.
    """
    accepts = [part.split(";")[0].strip() for part in accept_header.split(",")]
    if not ({"application/json", "text/event-stream"} & set(accepts)):
        return 406, "application/json", b'{"error":"Accept must include application/json or text/event-stream"}'
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        error = _jsonrpc_error(None, JSONRPC_PARSE_ERROR, "parse error")
        return 400, "application/json", json.dumps(error).encode()
    try:
        if isinstance(payload, list):
            responses = [item for item in (handle_jsonrpc(item) for item in payload) if item is not None]
            data = json.dumps(responses, ensure_ascii=False).encode()
        else:
            response = handle_jsonrpc(payload)
            if response is None:
                return 202, "application/json", b""
            data = json.dumps(response, ensure_ascii=False).encode()
    except ValueError as error:
        error_response = _jsonrpc_error(payload.get("id") if isinstance(payload, dict) else None, JSONRPC_INVALID_REQUEST, str(error) or "invalid request")
        data = json.dumps(error_response, ensure_ascii=False).encode()
        return 400, "application/json", data
    return 200, "application/json", data


class McpHandler:
    """Minimal stdlib HTTP handler for the MCP endpoint."""

    def __init__(self) -> None:
        self.timeout = 30

    def __call__(self, environ: dict, start_response) -> list[bytes]:
        length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        if length <= 0 or length > 4 * 1024 * 1024:
            start_response("400 Bad Request", [("Content-Type", "application/json")])
            return [b'{"error":"invalid request body"}']
        body = environ["wsgi.input"].read(length)
        status, content_type, data = handle_http_bytes(body, environ.get("HTTP_ACCEPT", ""))
        reason = {200: "OK", 202: "Accepted", 400: "Bad Request", 406: "Not Acceptable"}.get(status, "OK")
        start_response(f"{status} {reason}", [("Content-Type", content_type), ("Cache-Control", "no-store")])
        return [data]


def _self_test() -> int:
    checks = []
    identity = api.v1_identity()
    checks.append(("v1_identity returns pubskill-lib.api envelope", identity["schema"] == "pubskill-lib.api"))
    checks.append(("v1_list_skills returns 44 skills", api.v1_list_skills()["skill_count"] == 44))

    initialize = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "self-test", "version": "0"}}})
    checks.append(("initialize negotiates 2025-11-25", initialize["result"]["protocolVersion"] == PROTOCOL_VERSION))

    listed = handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    checks.append(("tools/list exposes all 7 pubskill tools", names == {tool["name"] for tool in TOOLS}))

    called = handle_jsonrpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "pubskill_list_skills", "arguments": {}}})
    text = json.loads(called["result"]["content"][0]["text"])
    checks.append(("tools/call pubskill_list_skills works", text["skill_count"] == 44 and not called["result"]["isError"]))

    called = handle_jsonrpc({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "pubskill_get_skill", "arguments": {"name": "msdmd"}}})
    text = json.loads(called["result"]["content"][0]["text"])
    checks.append(("tools/call pubskill_get_skill works", text["skill"]["name"] == "msdmd"))

    called = handle_jsonrpc({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "pubskill_resolve_skills", "arguments": {"query": "metadata collection"}}})
    text = json.loads(called["result"]["content"][0]["text"])
    checks.append(("tools/call pubskill_resolve_skills returns candidates", "msdmd" in [item["name"] for item in text["candidates"]]))

    called = handle_jsonrpc({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "pubskill_collect_metadata", "arguments": {"repo_url": "https://example.com/owner/repo"}}})
    checks.append(("tools/call collect rejects disallowed host", called["result"]["isError"] is True))

    failed = 0
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
        failed += 0 if passed else 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return _self_test()
    # Serve MCP over the same stdlib HTTP server pattern as service.py.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    port = int(__import__("os").environ.get("PORT", "8080"))

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0 or length > 4 * 1024 * 1024:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"invalid request body"}')
                return
            status, content_type, data = handle_http_bytes(
                self.rfile.read(length), self.headers.get("Accept", "")
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):  # noqa: A002
            return

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
