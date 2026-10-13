from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import service
from pubskill_lib.acquisition import AcquisitionError


class ServiceBoundaryTests(unittest.TestCase):
    def test_repo_url_allowlist_accepts_supported_https_hosts(self) -> None:
        accepted = (
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "https://gitlab.com/group/subgroup/repo.git",
            "https://bitbucket.org/owner/repo",
            "https://codeberg.org/owner/repo",
            "https://git.sr.ht/~owner/repo",
        )
        for value in accepted:
            with self.subTest(value=value):
                self.assertTrue(service.valid_repo_url(value))

    def test_repo_url_allowlist_rejects_credential_and_routing_escapes(self) -> None:
        rejected = (
            "http://github.com/owner/repo",
            "https://user@github.com/owner/repo",
            "https://github.com:443/owner/repo",
            "https://github.com/owner/../repo",
            "https://github.com/owner/repo?ref=main",
            "https://github.com/owner/repo#fragment",
            "https://github.com.evil.example/owner/repo",
            "https://example.com/owner/repo",
            "https://github.com/owner",
        )
        for value in rejected:
            with self.subTest(value=value):
                self.assertFalse(service.valid_repo_url(value))

    def test_inspection_is_explicitly_static(self) -> None:
        static_result = {
            "target": {"remote": "https://github.com/owner/repo", "commit": "abc"},
            "findings": [],
            "hmmm": [],
        }

        @contextmanager
        def fake_acquire(*args, **kwargs):
            yield SimpleNamespace(
                path=Path(tempfile.gettempdir()) / "fake-repo",
                limits={"max_per_file_bytes": 2 * 1024 * 1024},
            )

        with (
            patch.object(service, "acquire_repository", side_effect=fake_acquire),
            patch.object(service, "audit_path", return_value=static_result) as audit,
        ):
            result = service.run_inspection("https://github.com/owner/repo")

        audit.assert_called_once()
        scope = result["inspection_scope"]
        self.assertTrue(scope["static_only"])
        self.assertFalse(scope["executes_target_code"])
        self.assertFalse(scope["installs_target_dependencies"])
        self.assertFalse(scope["runs_target_tests"])
        self.assertFalse(scope["runtime_verified"])

    def test_inspection_enforces_per_file_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "big.txt").write_bytes(b"x" * (2 * 1024 * 1024 + 1))

            @contextmanager
            def fake_acquire(*args, **kwargs):
                yield SimpleNamespace(path=root, limits={"max_per_file_bytes": 2 * 1024 * 1024})

            with patch.object(service, "acquire_repository", side_effect=fake_acquire):
                with self.assertRaises(AcquisitionError):
                    service.run_inspection("https://github.com/owner/repo")

    def test_inspection_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to(root / "does-not-matter")

            @contextmanager
            def fake_acquire(*args, **kwargs):
                yield SimpleNamespace(path=root, limits={"max_per_file_bytes": 2 * 1024 * 1024})

            with patch.object(service, "acquire_repository", side_effect=fake_acquire):
                with self.assertRaises(AcquisitionError):
                    service.run_inspection("https://github.com/owner/repo")

    def test_paid_audit_functions_are_removed(self) -> None:
        for name in (
            "audit_pricing",
            "create_checkout",
            "stripe_api",
            "stripe_session",
            "paid_order",
            "paid_repos",
            "operator_authorized",
            "run_audit_batch",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(service, name))

    def test_invalid_repository_is_rejected_before_clone(self) -> None:
        with patch("pubskill_lib.acquisition.subprocess.run") as run:
            with self.assertRaises(AcquisitionError):
                service.run_inspection("https://example.com/owner/repo")
        run.assert_not_called()

    def test_requirement_arrays_are_capped_and_deduplicated(self) -> None:
        self.assertEqual(
            service._validated_requirements(["a", "b", "a"], "require_sources"),
            ("a", "b"),
        )
        with self.assertRaises(ValueError):
            service._validated_requirements([str(i) for i in range(21)], "require_sources")
        with self.assertRaises(ValueError):
            service._validated_requirements(["x" * 257], "require_sources")
        with self.assertRaises(ValueError):
            service._validated_requirements([1], "require_facts")

    def test_query_limits_are_validated_before_conversion(self) -> None:
        self.assertEqual(service.api.validate_limit(None, 200, 1000), 200)
        self.assertEqual(service.api.validate_limit(5, 200, 1000), 5)
        for bad in ({}, True, 0, 1001, "5"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    service.api.validate_limit(bad, 200, 1000)

    def test_max_workers_reads_environment(self) -> None:
        with patch.dict("os.environ", {"PUBSKILL_MAX_WORKERS": "2"}):
            self.assertEqual(service.max_workers(), 2)

    def test_concurrent_requests_are_bounded(self) -> None:
        import http.client

        entered = threading.Event()

        def slow_run(*args, **kwargs):
            entered.set()
            time.sleep(0.5)
            return {"findings": [], "hmmm": [], "target": {}}

        with patch.object(service, "WORKER_SEMAPHORE", threading.BoundedSemaphore(1)):
            with patch.object(service, "run_inspection", side_effect=slow_run):
                server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
                server.daemon_threads = True
                port = server.server_address[1]

                def serve() -> None:
                    server.handle_request()
                    server.handle_request()

                thread = threading.Thread(target=serve, daemon=True)
                thread.start()

                def post() -> int:
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    connection.request(
                        "POST",
                        "/inspect",
                        body=json.dumps({"repo_url": "https://github.com/owner/repo"}),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    status = response.status
                    response.read()
                    connection.close()
                    return status

                first = threading.Thread(target=post)
                first.start()
                self.assertTrue(entered.wait(timeout=5))
                second_status = post()
                first.join(timeout=5)
                thread.join(timeout=5)
                server.server_close()
                self.assertEqual(second_status, 429)

    def test_retired_endpoints_return_410_before_body_parsing(self) -> None:
        import http.client

        server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        server.daemon_threads = True
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("POST", "/audit", body=b"", headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        self.assertEqual(response.status, 410)
        response.read()
        connection.close()
        thread.join(timeout=5)
        server.server_close()

    def test_catalog_get_requests_are_bounded(self) -> None:
        import http.client

        entered = threading.Event()
        original_identity = service.api.v1_identity

        def slow_identity(*args, **kwargs):
            entered.set()
            time.sleep(0.5)
            return original_identity()

        with patch.object(service, "WORKER_SEMAPHORE", threading.BoundedSemaphore(1)):
            with patch.object(service.api, "v1_identity", side_effect=slow_identity):
                server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
                server.daemon_threads = True
                port = server.server_address[1]

                def serve() -> None:
                    server.handle_request()
                    server.handle_request()

                thread = threading.Thread(target=serve, daemon=True)
                thread.start()

                def get() -> int:
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    connection.request("GET", "/v1/identity")
                    response = connection.getresponse()
                    status = response.status
                    response.read()
                    connection.close()
                    return status

                first = threading.Thread(target=get)
                first.start()
                self.assertTrue(entered.wait(timeout=5))
                second_status = get()
                first.join(timeout=5)
                thread.join(timeout=5)
                server.server_close()
                self.assertEqual(second_status, 429)

    def test_skill_runtime_ignore_excludes_caches(self) -> None:
        from pubskill_lib.packaging_helpers import ignore_skill_runtime

        ignored = ignore_skill_runtime(".", ["__pycache__", "node_modules", "x.pyc", "real.txt"])
        self.assertEqual(ignored, {"__pycache__", "node_modules", "x.pyc"})


if __name__ == "__main__":
    unittest.main()
