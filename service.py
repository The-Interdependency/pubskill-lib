"""Hosted pubskill service.

Schema-1 static inspection (`POST /inspect`) and the retired audit endpoints
remain unchanged. The versioned `/v1/*` surface adds read-only catalog
retrieval and schema-2 MSDMD collection/query through the same bounded
repository acquisition path. All application logic lives in
`pubskill_lib.api`; this module is only the HTTP transport.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as _ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pubskill_lib import api, mcp_server
from pubskill_lib.acquisition import (
    AcquisitionError,
    AcquisitionTimeoutError,
    acquire_repository,
    valid_repo_url,
)
from pubskill_lib.audit import audit_path
from pubskill_lib.collections import CollectionError, CollectionTimeoutError
from pubskill_lib.metapat_adapter import MetapatUnavailable
from pubskill_lib.reaper import enable_child_subreaper

# Collection outputs are bounded at 8 MiB by the advertised API; JSON
# re-encoding and envelope fields can exceed that, so request bodies accept
# up to twice the collection-output bound for HTTP and MCP query round-trips.
MAX_REQUEST_BYTES = 12 * 1024 * 1024
MCP_MAX_REQUEST_BYTES = 16 * 1024 * 1024
BODY_READ_TIMEOUT_SECONDS = 10

_INSPECT_FIELDS = {"repo_url"}
_COLLECT_FIELDS = {"repo_url", "revision", "require_sources", "require_facts"}
_QUERY_FIELDS = {
    "collection",
    "repo_url",
    "revision",
    "convention",
    "fact_kind",
    "standing",
    "subject_contains",
    "path_glob",
    "diagnostic_status",
    "diagnostics_only",
    "limit",
}
_RESOLVE_FIELDS = {"query", "limit"}


def run_inspection(repo_url: str) -> dict:
    """Clone one public repository and run static inspection only."""
    repo_url = str(repo_url or "").strip()
    with acquire_repository(repo_url) as acquired:
        per_file_limit = acquired.limits["max_per_file_bytes"]
        for path in acquired.path.rglob("*"):
            if any(part == ".git" for part in path.parts):
                continue
            if path.is_symlink():
                raise AcquisitionError(
                    f"symlinks are not permitted in inspected checkouts: "
                    f"{path.relative_to(acquired.path)}"
                )
            if not path.is_file():
                continue
            if path.stat().st_size > per_file_limit:
                raise AcquisitionError(
                    f"file exceeds per-file limit {per_file_limit}: "
                    f"{path.relative_to(acquired.path)}"
                )
        result = audit_path(acquired.path)
        result["inspection_scope"] = {
            "static_only": True,
            "executes_target_code": False,
            "installs_target_dependencies": False,
            "runs_target_tests": False,
            "runtime_verified": False,
        }
        return result


def _validated_requirements(value: object, name: str) -> tuple[str, ...]:
    return api.validate_requirement_arrays(value, name)


def max_workers() -> int:
    return int(os.environ.get("PUBSKILL_MAX_WORKERS", "4"))


def max_body_readers() -> int:
    return int(os.environ.get("PUBSKILL_MAX_BODY_READERS", "8"))


WORKER_SEMAPHORE = threading.BoundedSemaphore(max_workers())
BODY_READER_SEMAPHORE = threading.BoundedSemaphore(max_body_readers())


def _read_body_bounded(rfile, length: int, timeout_seconds: int) -> bytes:
    """Read exactly ``length`` bytes under an absolute deadline.

    Each blocking read's socket timeout is set to the remaining deadline so a
    trickling client cannot keep individual reads alive past the total bound.
    """
    deadline = time.monotonic() + timeout_seconds
    chunks: list[bytes] = []
    remaining = length
    while remaining > 0:
        remaining_time = deadline - time.monotonic()
        if remaining_time <= 0:
            raise TimeoutError("request body timed out")
        # The caller set a socket timeout before calling; tighten it to the
        # remaining deadline so every blocking read honors the total bound.
        sock = getattr(rfile, "raw", None)
        if sock is not None:
            sock = getattr(sock, "_sock", sock)
        else:
            sock = getattr(rfile, "_sock", None)
        if sock is not None and hasattr(sock, "settimeout"):
            sock.settimeout(max(0.05, remaining_time))
        chunk = rfile.read(min(65536, remaining))
        if not chunk:
            raise ConnectionError("request body truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class Handler(BaseHTTPRequestHandler):
    def reply(self, status: int, body: object) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write_with_timeout(data)

    def _write_with_timeout(self, data: bytes) -> None:
        # A client that stops reading must not strand the worker semaphore
        # inside wfile.write; bound the write with a socket timeout.
        try:
            self.request.settimeout(BODY_READ_TIMEOUT_SECONDS)
            self.wfile.write(data)
        except (socket.timeout, TimeoutError, OSError):
            pass
        finally:
            self.request.settimeout(None)

    def page(self) -> None:
        data = Path("index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write_with_timeout(data)

    def request_json(self) -> dict:
        body = json.loads(self.raw_body)
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
        return body

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            return self.page()
        if path == "/mcp":
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not WORKER_SEMAPHORE.acquire(blocking=False):
            return self.reply(429, {"error": "too many concurrent operations"})
        try:
            if path == "/v1/identity":
                return self.reply(200, api.v1_identity())
            if path == "/v1/skills":
                return self.reply(200, api.v1_list_skills())
            if path == "/v1/metapat/catalog":
                return self.reply(200, api.v1_metapat_catalog())
            segments = [segment for segment in path.split("/") if segment]
            if len(segments) == 3 and segments[0] == "v1" and segments[1] == "skills":
                return self.reply(200, api.v1_get_skill(segments[2]))
            if (
                len(segments) == 4
                and segments[0] == "v1"
                and segments[1] == "skills"
                and segments[3] == "resource"
            ):
                resource_path = (parse_qs(parsed.query).get("path") or [""])[0]
                return self.reply(200, api.v1_get_resource(segments[2], resource_path))
            return self.reply(404, {"error": "not found"})
        except MetapatUnavailable as exc:
            return self.reply(404, {"error": str(exc) or "metapat adapter not enabled"})
        except (ValueError, KeyError, RuntimeError) as exc:
            return self.reply(400, {"error": str(exc) or "invalid request"})
        finally:
            WORKER_SEMAPHORE.release()

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path in {"/audit", "/checkout", "/paid", "/operator/audit"}:
            return self.reply(
                410,
                {
                    "error": "retired endpoint",
                    "replacement": "/inspect",
                    "reason": "static inspection is not a complete repository audit",
                },
            )
        limit = MCP_MAX_REQUEST_BYTES if path == "/mcp" else MAX_REQUEST_BYTES
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > limit:
            return self.reply(400, {"error": "invalid request body"})
        # Bound concurrent body readers separately, then read under an
        # absolute deadline before occupying a worker slot, so neither slow
        # clients nor slow readers can pin the operation semaphore.
        if not BODY_READER_SEMAPHORE.acquire(blocking=False):
            return self.reply(429, {"error": "too many concurrent request bodies"})
        try:
            self.request.settimeout(BODY_READ_TIMEOUT_SECONDS)
            self.raw_body = _read_body_bounded(self.rfile, length, BODY_READ_TIMEOUT_SECONDS)
        except (socket.timeout, TimeoutError, OSError):
            return self.reply(408, {"error": "request body timed out"})
        finally:
            self.request.settimeout(None)
            BODY_READER_SEMAPHORE.release()
        if not WORKER_SEMAPHORE.acquire(blocking=False):
            return self.reply(429, {"error": "too many concurrent operations"})
        try:
            self._handle_post()
        finally:
            WORKER_SEMAPHORE.release()

    def _handle_post(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/inspect":
            try:
                body = self.request_json()
                api.reject_unknown_fields(body, _INSPECT_FIELDS, "inspect")
                result = run_inspection(body["repo_url"])
                return self.reply(200, result)
            except AcquisitionTimeoutError:
                return self.reply(504, {"error": "repository inspection timed out"})
            except (ValueError, KeyError, json.JSONDecodeError, AcquisitionError) as exc:
                return self.reply(400, {"error": str(exc) or "invalid request"})
            except Exception as exc:
                print(f"inspection failure: {exc!r}", flush=True)
                return self.reply(500, {"error": "inspection failed"})

        if path == "/mcp":
            status, content_type, data = mcp_server.handle_http_bytes(
                self.raw_body,
                self.headers.get("Accept", ""),
                self.headers.get("Origin"),
                self.headers.get("MCP-Protocol-Version"),
                self.headers.get("Content-Type", ""),
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self._write_with_timeout(data)
            return

        try:
            if path == "/v1/skills/resolve":
                body = api.reject_unknown_fields(self.request_json(), _RESOLVE_FIELDS, "skills.resolve")
                return self.reply(
                    200,
                    api.v1_resolve(
                        body["query"],
                        limit=api.validate_limit(body.get("limit"), 10, 50),
                    ),
                )
            if path == "/v1/msdmd/collect":
                body = api.reject_unknown_fields(self.request_json(), _COLLECT_FIELDS, "msdmd.collect")
                return self.reply(
                    200,
                    api.v1_collect(
                        body["repo_url"],
                        revision=body.get("revision"),
                        require_sources=_validated_requirements(body.get("require_sources"), "require_sources"),
                        require_facts=_validated_requirements(body.get("require_facts"), "require_facts"),
                    ),
                )
            if path == "/v1/msdmd/query":
                body = api.reject_unknown_fields(self.request_json(), _QUERY_FIELDS, "msdmd.query")
                return self.reply(
                    200,
                    api.v1_query(
                        collection=body.get("collection"),
                        repo_url=api.validate_optional_str(body.get("repo_url"), "repo_url"),
                        revision=api.validate_optional_str(body.get("revision"), "revision"),
                        convention=api.validate_optional_str(body.get("convention"), "convention"),
                        fact_kind=api.validate_optional_str(body.get("fact_kind"), "fact_kind"),
                        standing=api.validate_optional_str(body.get("standing"), "standing"),
                        subject_contains=api.validate_optional_str(body.get("subject_contains"), "subject_contains"),
                        path_glob=api.validate_optional_str(body.get("path_glob"), "path_glob"),
                        diagnostic_status=api.validate_optional_str(body.get("diagnostic_status"), "diagnostic_status"),
                        diagnostics_only=api.validate_bool(body.get("diagnostics_only"), "diagnostics_only"),
                        limit=api.validate_limit(body.get("limit"), 200, 1000),
                    ),
                )
            if path == "/v1/metapat/recurrence":
                body = self.request_json()
                return self.reply(200, api.v1_metapat_recurrence(body))
            return self.reply(404, {"error": "not found"})
        except MetapatUnavailable as exc:
            return self.reply(404, {"error": str(exc) or "metapat adapter not enabled"})
        except (AcquisitionTimeoutError, CollectionTimeoutError):
            return self.reply(504, {"error": "operation timed out"})
        except (ValueError, KeyError, json.JSONDecodeError, AcquisitionError, CollectionError) as exc:
            return self.reply(400, {"error": str(exc) or "invalid request"})
        except Exception as exc:
            print(f"v1 failure: {exc!r}", flush=True)
            return self.reply(500, {"error": "operation failed"})


HEADER_READ_TIMEOUT_SECONDS = 10
MAX_CONNECTIONS = int(os.environ.get("PUBSKILL_MAX_CONNECTIONS", "32"))


class ThreadingHTTPServer(_ThreadingHTTPServer):
    """Threading server with bounded connections and an absolute header deadline.

    ``ThreadingHTTPServer`` would otherwise create an unrestricted thread per
    accepted socket with no deadline before the first header byte, so a slow
    client could exhaust threads and file descriptors without acquiring any
    semaphore. A connection-count semaphore bounds admission, and a timer
    closes each socket if headers have not completed within the deadline.
    """

    daemon_threads = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.connection_semaphore = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self._header_timers: dict[object, threading.Timer] = {}

    def _close_connection(self, request) -> None:
        try:
            request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            request.close()
        except OSError:
            pass

    def process_request(self, request, client_address):
        if not self.connection_semaphore.acquire(blocking=False):
            self._close_connection(request)
            return
        request.settimeout(HEADER_READ_TIMEOUT_SECONDS)
        timer = threading.Timer(HEADER_READ_TIMEOUT_SECONDS, self._close_connection, args=(request,))
        timer.daemon = True
        timer.start()
        self._header_timers[request] = timer
        try:
            super().process_request(request, client_address)
        except Exception:
            self.shutdown_request(request)
            self.handle_error(request, client_address)

    def shutdown_request(self, request):
        timer = self._header_timers.pop(request, None)
        if timer is not None:
            timer.cancel()
        try:
            super().shutdown_request(request)
        finally:
            self.connection_semaphore.release()


def main() -> None:
    enable_child_subreaper()
    ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
        Handler,
    ).serve_forever()


if __name__ == "__main__":
    main()
