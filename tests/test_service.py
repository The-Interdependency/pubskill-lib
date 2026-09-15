from __future__ import annotations

import os
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

    def test_purchase_repo_counts_are_exact_and_unique(self) -> None:
        one = ["https://github.com/owner/repo"]
        five = [f"https://github.com/owner/repo-{index}" for index in range(5)]
        self.assertEqual(service.validated_repo_urls(one, 1), one)
        self.assertEqual(service.validated_repo_urls(five, 5), five)

        with self.assertRaises(ValueError):
            service.validated_repo_urls(one, 5)
        with self.assertRaises(ValueError):
            service.validated_repo_urls(one * 5, 5)
        with self.assertRaises(ValueError):
            service.validated_repo_urls(
                ["https://github.com/owner/a", "https://github.com/owner/b"]
            )

    def test_paid_repos_binds_live_session_tier_amount_and_repositories(self) -> None:
        session = {
            "payment_status": "paid",
            "status": "complete",
            "mode": "payment",
            "livemode": True,
            "currency": "usd",
            "amount_total": 500,
            "metadata": {
                "pubskill_product": "audit",
                "pubskill_tier": "single",
                "repo_count": "1",
                "repo_1": "https://codeberg.org/owner/repo",
            },
        }
        self.assertEqual(
            service.paid_repos(session),
            ("single", ["https://codeberg.org/owner/repo"]),
        )

        for field, value in (
            ("payment_status", "unpaid"),
            ("status", "open"),
            ("mode", "setup"),
            ("livemode", False),
            ("currency", "eur"),
            ("amount_total", 501),
        ):
            altered = dict(session)
            altered[field] = value
            with self.subTest(field=field):
                with self.assertRaises(PermissionError):
                    service.paid_repos(altered)

    def test_paid_repos_rejects_foreign_or_malformed_metadata(self) -> None:
        base = {
            "payment_status": "paid",
            "status": "complete",
            "mode": "payment",
            "livemode": True,
            "currency": "usd",
            "amount_total": 2000,
        }
        bad_metadata = (
            {},
            {
                "pubskill_product": "other",
                "pubskill_tier": "bundle5",
                "repo_count": "5",
            },
            {
                "pubskill_product": "audit",
                "pubskill_tier": "bundle5",
                "repo_count": "4",
            },
            {
                "pubskill_product": "audit",
                "pubskill_tier": "bundle5",
                "repo_count": "5",
                "repo_1": "https://example.com/a/b",
                "repo_2": "https://github.com/a/b",
                "repo_3": "https://github.com/c/d",
                "repo_4": "https://github.com/e/f",
                "repo_5": "https://github.com/g/h",
            },
        )
        for metadata in bad_metadata:
            session = dict(base)
            session["metadata"] = metadata
            with self.subTest(metadata=metadata):
                with self.assertRaises((PermissionError, ValueError)):
                    service.paid_repos(session)

    def test_operator_code_is_server_side_and_constant_time_comparable(self) -> None:
        with patch.dict(os.environ, {"PUBSKILL_OPERATOR_CODE": "secret-code"}, clear=False):
            self.assertTrue(service.operator_authorized("secret-code"))
            self.assertFalse(service.operator_authorized("wrong"))
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(service.operator_authorized("secret-code"))

    def test_checkout_form_binds_exact_repository_metadata(self) -> None:
        captured = {}

        def fake_stripe_api(path, form=None):
            captured["path"] = path
            captured["form"] = dict(form or [])
            return {"id": "cs_test", "url": "https://checkout.stripe.com/test"}

        repos = [f"https://github.com/owner/repo-{index}" for index in range(5)]
        with patch.object(service, "stripe_api", fake_stripe_api):
            session = service.create_checkout(repos, "bundle5")

        self.assertEqual(session["id"], "cs_test")
        self.assertEqual(captured["path"], "checkout/sessions")
        self.assertEqual(
            captured["form"]["line_items[0][price]"],
            service.AUDIT_TIERS["bundle5"]["price_id"],
        )
        self.assertEqual(captured["form"]["metadata[pubskill_tier]"], "bundle5")
        self.assertEqual(captured["form"]["metadata[repo_count]"], "5")
        for index, repo in enumerate(repos, start=1):
            self.assertEqual(captured["form"][f"metadata[repo_{index}]"], repo)


if __name__ == "__main__":
    unittest.main()
