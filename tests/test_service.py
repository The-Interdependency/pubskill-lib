from __future__ import annotations

import unittest
from unittest.mock import patch

import service


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
        with (
            patch.object(service.subprocess, "run") as run,
            patch.object(service, "audit_path", return_value=static_result),
        ):
            result = service.run_inspection("https://github.com/owner/repo")

        run.assert_called_once()
        scope = result["inspection_scope"]
        self.assertTrue(scope["static_only"])
        self.assertFalse(scope["executes_target_code"])
        self.assertFalse(scope["installs_target_dependencies"])
        self.assertFalse(scope["runs_target_tests"])
        self.assertFalse(scope["runtime_verified"])

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
        with patch.object(service.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                service.run_inspection("https://example.com/owner/repo")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
