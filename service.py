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
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pubskill_lib import api
from pubskill_lib.acquisition import AcquisitionError, acquire_repository, valid_repo_url
from pubskill_lib.audit import audit_path
from pubskill_lib.collections import CollectionError

MAX_REQUEST_BYTES = 1024 * 1024

_INSPECT_FIELDS = {"repo_url"}
_COLLECT_FIELDS = {"repo_url", "revision", "require_sources", "require_facts", "limits"}
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


def _reject_unknown_fields(body: dict, allowed: set[str], name: str) -> dict:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ValueError(f"unknown fields in {name}: {', '.join(unknown)}")
    return body


def run_inspection(repo_url: str) -> dict:
    """Clone one public repository and run static inspection only."""
    repo_url = str(repo_url or "").strip()
    with acquire_repository(repo_url) as acquired:
        result = audit_path(acquired.path)
        result["inspection_scope"] = {
            "static_only": True,
            "executes_target_code": False,
            "installs_target_dependencies": False,
            "runs_target_tests": False,
            "runtime_verified": False,
        }
        return result


class Handler(BaseHTTPRequestHandler):
    def reply(self, status: int, body: object) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def page(self) -> None:
        data = Path("index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def request_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
        return body

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            return self.page()
        try:
            if path == "/v1/identity":
                return self.reply(200, api.v1_identity())
            if path == "/v1/skills":
                return self.reply(200, api.v1_list_skills())
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
        except (ValueError, KeyError, RuntimeError) as exc:
            return self.reply(400, {"error": str(exc) or "invalid request"})

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/inspect":
            try:
                body = self.request_json()
                _reject_unknown_fields(body, _INSPECT_FIELDS, "inspect")
                result = run_inspection(body["repo_url"])
                return self.reply(200, result)
            except (ValueError, KeyError, json.JSONDecodeError, AcquisitionError) as exc:
                return self.reply(400, {"error": str(exc) or "invalid request"})
            except subprocess.TimeoutExpired:
                return self.reply(504, {"error": "repository inspection timed out"})
            except Exception as exc:
                print(f"inspection failure: {exc!r}", flush=True)
                return self.reply(500, {"error": "inspection failed"})

        if path in {"/audit", "/checkout", "/paid", "/operator/audit"}:
            return self.reply(
                410,
                {
                    "error": "retired endpoint",
                    "replacement": "/inspect",
                    "reason": "static inspection is not a complete repository audit",
                },
            )

        try:
            if path == "/v1/skills/resolve":
                body = _reject_unknown_fields(self.request_json(), _RESOLVE_FIELDS, "skills.resolve")
                return self.reply(
                    200,
                    api.v1_resolve(
                        body["query"],
                        limit=body.get("limit"),
                    ),
                )
            if path == "/v1/msdmd/collect":
                body = _reject_unknown_fields(self.request_json(), _COLLECT_FIELDS, "msdmd.collect")
                return self.reply(
                    200,
                    api.v1_collect(
                        body["repo_url"],
                        revision=body.get("revision"),
                        require_sources=tuple(body.get("require_sources") or ()),
                        require_facts=tuple(body.get("require_facts") or ()),
                        limits=body.get("limits"),
                    ),
                )
            if path == "/v1/msdmd/query":
                body = _reject_unknown_fields(self.request_json(), _QUERY_FIELDS, "msdmd.query")
                return self.reply(
                    200,
                    api.v1_query(
                        collection=body.get("collection"),
                        repo_url=body.get("repo_url"),
                        revision=body.get("revision"),
                        convention=body.get("convention"),
                        fact_kind=body.get("fact_kind"),
                        standing=body.get("standing"),
                        subject_contains=body.get("subject_contains"),
                        path_glob=body.get("path_glob"),
                        diagnostic_status=body.get("diagnostic_status"),
                        diagnostics_only=bool(body.get("diagnostics_only", False)),
                        limit=int(body.get("limit", 200)),
                    ),
                )
            return self.reply(404, {"error": "not found"})
        except (ValueError, KeyError, json.JSONDecodeError, AcquisitionError, CollectionError) as exc:
            return self.reply(400, {"error": str(exc) or "invalid request"})
        except subprocess.TimeoutExpired:
            return self.reply(504, {"error": "operation timed out"})
        except Exception as exc:
            print(f"v1 failure: {exc!r}", flush=True)
            return self.reply(500, {"error": "operation failed"})


def main() -> None:
    ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
        Handler,
    ).serve_forever()


if __name__ == "__main__":
    main()
