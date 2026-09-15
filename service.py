"""Hosted static repository inspection service.

Usage: python service.py

This service clones supported public Git repositories and runs pubskill's
static inspector. It does not install target dependencies, execute target code
or tests, or claim runtime verification. A true repository audit requires a
separately isolated execution-and-receipt system and is not offered here yet.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pubskill_lib.audit import audit_path

ALLOWED_GIT_HOSTS = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "codeberg.org",
    "git.sr.ht",
}
MAX_REQUEST_BYTES = 1024 * 1024


def valid_repo_url(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False

    parts = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_GIT_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
        and len(parts) >= 2
        and ".." not in parts
    )


def run_inspection(repo_url):
    """Clone one public repository and run static inspection only."""
    repo_url = str(repo_url or "").strip()
    if not valid_repo_url(repo_url):
        raise ValueError("supported public Git repository required")

    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "repo")
        subprocess.run(
            ["git", "clone", "--depth=1", "--single-branch", repo_url, target],
            check=True,
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        result = audit_path(target)
        result["inspection_scope"] = {
            "static_only": True,
            "executes_target_code": False,
            "installs_target_dependencies": False,
            "runs_target_tests": False,
            "runtime_verified": False,
        }
        return result


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def page(self):
        data = Path("index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def request_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request")
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        if urlsplit(self.path).path == "/":
            return self.page()
        return self.reply(404, {"error": "not found"})

    def do_POST(self):
        path = urlsplit(self.path).path

        if path == "/inspect":
            try:
                body = self.request_json()
                result = run_inspection(body["repo_url"])
                return self.reply(200, result)
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                return self.reply(400, {"error": str(exc) or "invalid request"})
            except subprocess.TimeoutExpired:
                return self.reply(504, {"error": "repository inspection timed out"})
            except subprocess.CalledProcessError:
                return self.reply(400, {"error": "repository could not be cloned"})
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

        return self.reply(404, {"error": "not found"})


def main():
    ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
        Handler,
    ).serve_forever()


if __name__ == "__main__":
    main()
