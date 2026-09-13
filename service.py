import json
import os
import re
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pubskill_lib.audit import audit_path

REPO = re.compile(r"^https://github\.com/[^/]+/[^/]+(?:\.git)?$")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        data = Path("index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/audit":
            return self.reply(404, {"error": "not found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(min(length, 8192)))
            repo_url = body["repo_url"]

            if not REPO.fullmatch(repo_url):
                return self.reply(400, {"error": "public github.com repository required"})

            with tempfile.TemporaryDirectory() as tmp:
                target = os.path.join(tmp, "repo")
                subprocess.run(
                    ["git", "clone", "--depth=1", repo_url, target],
                    check=True,
                    timeout=120,
                )
                result = audit_path(target)

            self.reply(200, result)

        except Exception as exc:
            self.reply(500, {"error": str(exc)})


ThreadingHTTPServer(
    ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
    Handler,
).serve_forever()
