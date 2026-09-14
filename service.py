import base64
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen

from pubskill_lib.audit import audit_path

ALLOWED_GIT_HOSTS = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "codeberg.org",
    "git.sr.ht",
}
PAYMENT_LINK_ID = "plink_1UFLuMAyiOEDWiRnLUiYEx3Y"
PAYMENT_LINK_URL = "https://buy.stripe.com/14A6oG5Sk9MWg8z3UO5EY01"
PRICE_CENTS = 1900
FREE_FINDINGS = 3


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


def run_audit(repo_url):
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
        return audit_path(target)


def stripe_session(session_id):
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("payment verification is not configured")

    auth = base64.b64encode(f"{key}:".encode()).decode()
    request = Request(
        f"https://api.stripe.com/v1/checkout/sessions/{quote(session_id, safe='')}",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def paid_repo(session):
    if session.get("payment_status") != "paid":
        raise PermissionError("payment is not complete")
    if session.get("payment_link") != PAYMENT_LINK_ID:
        raise PermissionError("payment does not belong to this product")
    if session.get("currency") != "usd" or session.get("amount_total") != PRICE_CENTS:
        raise PermissionError("payment amount does not match this product")

    for field in session.get("custom_fields") or []:
        if field.get("key") == "githubrepo" and field.get("type") == "text":
            repo_url = (field.get("text") or {}).get("value", "").strip()
            if valid_repo_url(repo_url):
                return repo_url

    raise ValueError("paid checkout is missing a valid supported Git repository URL")


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

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            return self.page()

        if parsed.path == "/paid":
            session_id = (parse_qs(parsed.query).get("session_id") or [""])[0]
            if not session_id:
                return self.reply(400, {"error": "missing checkout session"})
            try:
                session = stripe_session(session_id)
                repo_url = paid_repo(session)
                result = run_audit(repo_url)
                result["paid"] = True
                return self.reply(200, result)
            except PermissionError as exc:
                return self.reply(402, {"error": str(exc)})
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            except Exception as exc:
                print(f"paid audit failure: {exc!r}", flush=True)
                return self.reply(500, {"error": "paid audit could not be verified or completed"})

        return self.reply(404, {"error": "not found"})

    def do_POST(self):
        if urlsplit(self.path).path != "/audit":
            return self.reply(404, {"error": "not found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 8192:
                return self.reply(400, {"error": "invalid request"})
            body = json.loads(self.rfile.read(length))
            repo_url = str(body["repo_url"]).strip()
            result = run_audit(repo_url)

            findings = result.get("findings") or []
            preview = {
                "target": result.get("target"),
                "surfaces": result.get("surfaces"),
                "findings": findings[:FREE_FINDINGS],
                "total_findings": len(findings),
                "hmmm_count": len(result.get("hmmm") or []),
                "locked": len(findings) > FREE_FINDINGS or bool(result.get("hmmm")),
                "payment_link": PAYMENT_LINK_URL,
            }
            return self.reply(200, preview)

        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            return self.reply(400, {"error": str(exc) or "invalid request"})
        except subprocess.TimeoutExpired:
            return self.reply(504, {"error": "repository audit timed out"})
        except subprocess.CalledProcessError:
            return self.reply(400, {"error": "repository could not be cloned"})
        except Exception as exc:
            print(f"audit failure: {exc!r}", flush=True)
            return self.reply(500, {"error": "audit failed"})


ThreadingHTTPServer(
    ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
    Handler,
).serve_forever()
