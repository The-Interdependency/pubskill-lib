import base64
import hmac
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from pubskill_lib.audit import audit_path

ALLOWED_GIT_HOSTS = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "codeberg.org",
    "git.sr.ht",
}
AUDIT_TIERS = {
    "single": {
        "repositories": 1,
        "amount_cents": 500,
        "price_id": "price_1UFlntAyiOEDWiRnVtvKTiUB",
    },
    "bundle5": {
        "repositories": 5,
        "amount_cents": 2000,
        "price_id": "price_1UFlncAyiOEDWiRnJzM9ewHX",
    },
}
FREE_FINDINGS = 3
DEFAULT_SUCCESS_URL = (
    "https://pubskill.interdependentway.org/?session_id={CHECKOUT_SESSION_ID}"
)
DEFAULT_CANCEL_URL = "https://pubskill.interdependentway.org/"


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


def validated_repo_urls(values, expected_count=None):
    if not isinstance(values, list):
        raise ValueError("repository URLs must be a list")

    repo_urls = [str(value).strip() for value in values]
    if expected_count is not None and len(repo_urls) != expected_count:
        raise ValueError(f"exactly {expected_count} repository URL(s) required")
    if len(repo_urls) not in (1, 5):
        raise ValueError("audit purchases support 1 or 5 repositories")
    if any(not valid_repo_url(value) for value in repo_urls):
        raise ValueError("supported public Git repository required")
    if len(set(repo_urls)) != len(repo_urls):
        raise ValueError("duplicate repository URLs are not allowed")
    return repo_urls


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


def run_audit_batch(repo_urls):
    audits = []
    for repo_url in repo_urls:
        try:
            result = run_audit(repo_url)
            audits.append({"repo_url": repo_url, "result": result})
        except subprocess.TimeoutExpired:
            audits.append({"repo_url": repo_url, "error": "repository audit timed out"})
        except subprocess.CalledProcessError:
            audits.append({"repo_url": repo_url, "error": "repository could not be cloned"})
        except Exception as exc:
            print(f"audit failure for {repo_url!r}: {exc!r}", flush=True)
            audits.append({"repo_url": repo_url, "error": "repository audit failed"})
    return audits


def stripe_api(path, form=None):
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("payment verification is not configured")

    auth = base64.b64encode(f"{key}:".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    data = None
    if form is not None:
        data = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = Request(
        f"https://api.stripe.com/v1/{path.lstrip('/')}",
        data=data,
        headers=headers,
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def create_checkout(repo_urls, tier):
    config = AUDIT_TIERS.get(tier)
    if config is None:
        raise ValueError("unknown audit purchase")
    repo_urls = validated_repo_urls(repo_urls, config["repositories"])

    success_url = os.environ.get("PUBSKILL_SUCCESS_URL", DEFAULT_SUCCESS_URL)
    cancel_url = os.environ.get("PUBSKILL_CANCEL_URL", DEFAULT_CANCEL_URL)
    form = [
        ("mode", "payment"),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("line_items[0][price]", config["price_id"]),
        ("line_items[0][quantity]", "1"),
        ("client_reference_id", "pubskill-audit"),
        ("metadata[pubskill_product]", "audit"),
        ("metadata[pubskill_tier]", tier),
        ("metadata[repo_count]", str(config["repositories"])),
    ]
    for index, repo_url in enumerate(repo_urls, start=1):
        form.append((f"metadata[repo_{index}]", repo_url))

    session = stripe_api("checkout/sessions", form)
    if not session.get("id") or not session.get("url"):
        raise RuntimeError("checkout session did not return a payment URL")
    return session


def stripe_session(session_id):
    return stripe_api(f"checkout/sessions/{quote(session_id, safe='')}")


def paid_repos(session):
    if session.get("payment_status") != "paid" or session.get("status") != "complete":
        raise PermissionError("payment is not complete")
    if session.get("mode") != "payment":
        raise PermissionError("checkout session is not a payment")
    if not session.get("livemode"):
        raise PermissionError("checkout session is not live")

    metadata = session.get("metadata") or {}
    if metadata.get("pubskill_product") != "audit":
        raise PermissionError("payment does not belong to this product")

    tier = metadata.get("pubskill_tier")
    config = AUDIT_TIERS.get(tier)
    if config is None:
        raise PermissionError("payment tier is not recognized")
    if session.get("currency") != "usd" or session.get("amount_total") != config["amount_cents"]:
        raise PermissionError("payment amount does not match this product")
    if metadata.get("repo_count") != str(config["repositories"]):
        raise PermissionError("payment repository count does not match this product")

    repo_urls = [
        (metadata.get(f"repo_{index}") or "").strip()
        for index in range(1, config["repositories"] + 1)
    ]
    return tier, validated_repo_urls(repo_urls, config["repositories"])


def operator_authorized(code):
    expected = os.environ.get("PUBSKILL_OPERATOR_CODE", "")
    supplied = str(code or "")
    return bool(expected) and hmac.compare_digest(supplied, expected)


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
        if length <= 0 or length > 16384:
            raise ValueError("invalid request")
        return json.loads(self.rfile.read(length))

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
                tier, repo_urls = paid_repos(session)
                return self.reply(
                    200,
                    {
                        "paid": True,
                        "tier": tier,
                        "repository_count": len(repo_urls),
                        "audits": run_audit_batch(repo_urls),
                    },
                )
            except PermissionError as exc:
                return self.reply(402, {"error": str(exc)})
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            except Exception as exc:
                print(f"paid audit failure: {exc!r}", flush=True)
                return self.reply(500, {"error": "paid audit could not be verified or completed"})

        return self.reply(404, {"error": "not found"})

    def do_POST(self):
        path = urlsplit(self.path).path

        if path == "/audit":
            try:
                body = self.request_json()
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

        if path == "/checkout":
            try:
                body = self.request_json()
                tier = str(body["tier"]).strip()
                config = AUDIT_TIERS.get(tier)
                if config is None:
                    raise ValueError("unknown audit purchase")
                repo_urls = validated_repo_urls(body["repo_urls"], config["repositories"])
                session = create_checkout(repo_urls, tier)
                return self.reply(
                    200,
                    {
                        "checkout_url": session["url"],
                        "session_id": session["id"],
                    },
                )
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                return self.reply(400, {"error": str(exc) or "invalid request"})
            except Exception as exc:
                print(f"checkout failure: {exc!r}", flush=True)
                return self.reply(500, {"error": "checkout could not be created"})

        if path == "/operator/audit":
            try:
                body = self.request_json()
                if not operator_authorized(body.get("code")):
                    return self.reply(403, {"error": "access code not accepted"})
                repo_urls = validated_repo_urls(body["repo_urls"])
                tier = "single" if len(repo_urls) == 1 else "bundle5"
                return self.reply(
                    200,
                    {
                        "operator": True,
                        "tier": tier,
                        "repository_count": len(repo_urls),
                        "audits": run_audit_batch(repo_urls),
                    },
                )
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                return self.reply(400, {"error": str(exc) or "invalid request"})
            except Exception as exc:
                print(f"operator audit failure: {exc!r}", flush=True)
                return self.reply(500, {"error": "operator audit failed"})

        return self.reply(404, {"error": "not found"})


def main():
    ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
        Handler,
    ).serve_forever()


if __name__ == "__main__":
    main()
