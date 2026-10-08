"""MCP Streamable HTTP transport (specification 2025-11-25) for pubskill.

The transport is stateless JSON-over-HTTP. All tools call the same
`pubskill_lib.api` application functions used by the HTTP API; the MCP adapter
maintains no second catalog and performs no collection of its own.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import urlsplit

from . import __version__, api, metapat_adapter
from .acquisition import AcquisitionError
from .collections import CollectionError
from .metapat_adapter import MetapatUnavailable

PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = {PROTOCOL_VERSION}
SERVER_NAME = "pubskill-lib"

JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603

DEFAULT_ALLOWED_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}

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


def _metapat_evidence_schema() -> dict:
    string = {"type": "string", "minLength": 1}
    string_array = {"type": "array", "items": {"type": "string"}}
    optional_bool = {"type": ["boolean", "null"]}
    return {
        "type": "object",
        "properties": {
            "source_domain": string,
            "target_domain": string,
            "source_origin_id": string,
            "target_origin_id": string,
            "source_path_id": string,
            "target_path_id": string,
            "declared_invariants": string_array,
            "preserved_invariants": string_array,
            "mapping_complete": optional_bool,
            "replay_passed": optional_bool,
            "catalog_version": string,
            "catalog_digest": string,
            "catalog_module_ids": string_array,
            "equivalence_proof_id": {"type": ["string", "null"]},
            "shared_ancestry": string_array,
            "ancestry_resolved": {"type": "boolean"},
            "unresolved": string_array,
        },
        "required": [
            "source_domain",
            "target_domain",
            "source_origin_id",
            "target_origin_id",
            "source_path_id",
            "target_path_id",
            "declared_invariants",
            "preserved_invariants",
            "mapping_complete",
            "replay_passed",
            "catalog_version",
            "catalog_digest",
            "catalog_module_ids",
        ],
        "additionalProperties": False,
    }


METAPAT_TOOL = {
    "name": "pubskill_classify_recurrence",
    "description": "Adjudicate one fully typed METAPAT cross-domain structural-recurrence evidence record through the exact-pin, digest-checked optional adapter. Requires the METAPAT adapter to be enabled.",
    "inputSchema": {
        "type": "object",
        "properties": {"evidence": _metapat_evidence_schema()},
        "required": ["evidence"],
        "additionalProperties": False,
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    tools = list(TOOLS)
    if metapat_adapter.is_metapat_enabled():
        tools.append(METAPAT_TOOL)
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in tools
    ]


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _jsonrpc_result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _tool_content(text: str, *, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _require_str(arguments: dict, name: str) -> None:
    if name in arguments and not isinstance(arguments[name], str):
        raise ValueError(f"{name} must be a string")


def _require_optional_str(arguments: dict, name: str) -> None:
    _require_str(arguments, name)


def _require_str_list(arguments: dict, name: str) -> None:
    if name not in arguments:
        return
    value = arguments[name]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")


def _validate_arguments(name: str, arguments: dict) -> dict:
    """Validate tool arguments against the published schemas before dispatch."""
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be a JSON object")
    if name == "pubskill_identity" or name == "pubskill_list_skills":
        if arguments:
            raise ValueError("this tool takes no arguments")
    elif name == "pubskill_get_skill":
        _require_str(arguments, "name")
    elif name == "pubskill_get_resource":
        _require_str(arguments, "name")
        _require_str(arguments, "path")
    elif name == "pubskill_collect_metadata":
        _require_str(arguments, "repo_url")
        _require_optional_str(arguments, "revision")
        _require_str_list(arguments, "require_sources")
        _require_str_list(arguments, "require_facts")
    elif name == "pubskill_query_metadata":
        if "collection" in arguments and not isinstance(arguments["collection"], dict):
            raise ValueError("collection must be an object")
        for key in ("repo_url", "revision", "convention", "fact_kind", "standing", "subject_contains", "path_glob", "diagnostic_status"):
            _require_optional_str(arguments, key)
        if "diagnostics_only" in arguments and not isinstance(arguments["diagnostics_only"], bool):
            raise ValueError("diagnostics_only must be a boolean")
        if "limit" in arguments and (
            not isinstance(arguments["limit"], int)
            or isinstance(arguments["limit"], bool)
            or not 1 <= arguments["limit"] <= 1000
        ):
            raise ValueError("limit must be an integer between 1 and 1000")
    elif name == "pubskill_resolve_skills":
        _require_str(arguments, "query")
        if "limit" in arguments and (
            not isinstance(arguments["limit"], int)
            or isinstance(arguments["limit"], bool)
            or not 1 <= arguments["limit"] <= 50
        ):
            raise ValueError("limit must be an integer between 1 and 50")
    elif name == "pubskill_classify_recurrence":
        if "evidence" not in arguments or not isinstance(arguments["evidence"], dict):
            raise ValueError("evidence must be an object")
    else:
        raise ValueError(f"unknown tool: {name}")
    return arguments


def call_tool(name: str, arguments: dict) -> dict:
    """Execute one pubskill MCP tool against the shared application layer."""
    arguments = _validate_arguments(name, arguments)
    tool_names = {tool["name"] for tool in tool_schemas()}
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
    elif name == "pubskill_classify_recurrence":
        result = api.v1_metapat_recurrence(arguments["evidence"])
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
    is_notification = "id" not in payload
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    def respond(result: dict) -> dict | None:
        if is_notification:
            return None
        return _jsonrpc_result(request_id, result)

    def respond_error(code: int, message: str) -> dict | None:
        if is_notification:
            return None
        return _jsonrpc_error(request_id, code, message)

    if method == "initialize":
        return respond(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
                "instructions": (
                    "pubskill exposes the pinned skill-lib catalog and schema-2 "
                    "MSDMD collection/query as MCP tools. Schema-1 /inspect "
                    "remains a separate HTTP contract."
                ),
            }
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return respond({})
    if method == "tools/list":
        return respond({"tools": tool_schemas()})
    if method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return respond_error(JSONRPC_INVALID_PARAMS, "tools/call requires a tool name")
        try:
            return respond(call_tool(params["name"], params.get("arguments", {})))
        except (KeyError, ValueError, AcquisitionError, CollectionError, MetapatUnavailable) as error:
            return respond(_tool_content(str(error) or "invalid tool arguments", is_error=True))
    return respond_error(JSONRPC_METHOD_NOT_FOUND, f"method not found: {method}")


def _origin_allowed(origin_header: str | None) -> bool:
    if not origin_header:
        return True  # non-browser clients are not required to send Origin
    allowed_extra = {
        item.strip()
        for item in os.environ.get("PUBSKILL_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    if origin_header in allowed_extra:
        return True
    try:
        hostname = urlsplit(origin_header).hostname
    except ValueError:
        return False
    return hostname in DEFAULT_ALLOWED_ORIGIN_HOSTS


def handle_http_bytes(
    body: bytes,
    accept_header: str = "",
    origin_header: str | None = None,
    protocol_version_header: str | None = None,
) -> tuple[int, str, bytes]:
    """Handle one MCP Streamable HTTP request body.

    Returns (status, content_type, response_body). The transport is stateless;
    the server assigns no session id.
    """
    if not _origin_allowed(origin_header):
        return 403, "application/json", b'{"error":"Origin is not allowed"}'
    if protocol_version_header and protocol_version_header not in SUPPORTED_PROTOCOL_VERSIONS:
        error = _jsonrpc_error(None, JSONRPC_INVALID_REQUEST, f"unsupported MCP protocol version: {protocol_version_header}")
        return 400, "application/json", json.dumps(error).encode()
    accepts = {part.split(";")[0].strip() for part in accept_header.split(",")}
    if not {"application/json", "text/event-stream"}.issubset(accepts):
        return 406, "application/json", b'{"error":"Accept must include application/json and text/event-stream"}'
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        error = _jsonrpc_error(None, JSONRPC_PARSE_ERROR, "parse error")
        return 400, "application/json", json.dumps(error).encode()
    if isinstance(payload, list):
        error = _jsonrpc_error(None, JSONRPC_INVALID_REQUEST, "batch JSON-RPC requests are not supported")
        return 400, "application/json", json.dumps(error).encode()
    try:
        response = handle_jsonrpc(payload)
    except ValueError as error:
        error_response = _jsonrpc_error(
            payload.get("id") if isinstance(payload, dict) else None,
            JSONRPC_INVALID_REQUEST,
            str(error) or "invalid request",
        )
        return 400, "application/json", json.dumps(error_response).encode()
    if response is None:
        return 202, "application/json", b""
    return 200, "application/json", json.dumps(response, ensure_ascii=False).encode()


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
        status, content_type, data = handle_http_bytes(
            body,
            environ.get("HTTP_ACCEPT", ""),
            environ.get("HTTP_ORIGIN"),
            environ.get("HTTP_MCP_PROTOCOL_VERSION"),
        )
        reason = {200: "OK", 202: "Accepted", 400: "Bad Request", 403: "Forbidden", 406: "Not Acceptable"}.get(status, "OK")
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
    checks.append(("tools/list exposes exactly the enabled pubskill tools", names == {tool["name"] for tool in tool_schemas()}))

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

    bad_arguments = handle_jsonrpc({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "pubskill_resolve_skills", "arguments": {"query": "x", "limit": {}}}})
    checks.append(("tools/call rejects schema-invalid arguments as tool errors", bad_arguments["result"]["isError"] is True))

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
                self.rfile.read(length),
                self.headers.get("Accept", ""),
                self.headers.get("Origin"),
                self.headers.get("MCP-Protocol-Version"),
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
