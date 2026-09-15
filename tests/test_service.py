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

    def test_purchase_repo_counts_are_arbitrary_positive_and_unique(self) -> None:
        for count in (1, 2, 4, 5, 6, 10, 17):
            repos = [f"https://github.com/owner/repo-{index}" for index in range(count)]
            with self.subTest(count=count):
                self.assertEqual(service.validated_repo_urls(repos), repos)
                self.assertEqual(service.validated_repo_urls(repos, count), repos)

        with self.assertRaises(ValueError):
            service.validated_repo_urls([])
        with self.assertRaises(ValueError):
            service.validated_repo_urls(["https://github.com/owner/a"], 2)
        with self.assertRaises(ValueError):
            service.validated_repo_urls(
                ["https://github.com/owner/a", "https://github.com/owner/a"]
            )

    def test_every_fifth_audit_is_free(self) -> None:
        expected = {
            1: (1, 0, 500),
            4: (4, 0, 2000),
            5: (4, 1, 2000),
            6: (5, 1, 2500),
            9: (8, 1, 4000),
            10: (8, 2, 4000),
            11: (9, 2, 4500),
            25: (20, 5, 10000),
        }
        for count, (paid, free, amount) in expected.items():
            with self.subTest(count=count):
                pricing = service.audit_pricing(count)
                self.assertEqual(pricing["repository_count"], count)
                self.assertEqual(pricing["paid_count"], paid)
                self.assertEqual(pricing["free_count"], free)
                self.assertEqual(pricing["amount_cents"], amount)

        for invalid in (0, -1, 1.5, True, "5"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    service.audit_pricing(invalid)

    def test_repo_digest_is_order_bound(self) -> None:
        a = ["https://github.com/owner/a", "https://github.com/owner/b"]
        b = list(reversed(a))
        self.assertEqual(service.repo_digest(a), service.repo_digest(list(a)))
        self.assertNotEqual(service.repo_digest(a), service.repo_digest(b))

    def test_paid_repos_binds_live_session_price_count_and_repository_digest(self) -> None:
        repos = [f"https://codeberg.org/owner/repo-{index}" for index in range(6)]
        session = {
            "payment_status": "paid",
            "status": "complete",
            "mode": "payment",
            "livemode": True,
            "currency": "usd",
            "amount_total": 2500,
            "metadata": {
                "pubskill_product": "audit",
                "pricing_rule": "every_fifth_free",
                "repo_count": "6",
                "paid_count": "5",
                "free_count": "1",
                "repo_digest": service.repo_digest(repos),
            },
        }
        pricing, paid_repos = service.paid_repos(session, repos)
        self.assertEqual(paid_repos, repos)
        self.assertEqual(pricing["paid_count"], 5)
        self.assertEqual(pricing["free_count"], 1)

        for field, value in (
            ("payment_status", "unpaid"),
            ("status", "open"),
            ("mode", "setup"),
            ("livemode", False),
            ("currency", "eur"),
            ("amount_total", 2501),
        ):
            altered = dict(session)
            altered[field] = value
            with self.subTest(field=field):
                with self.assertRaises(PermissionError):
                    service.paid_repos(altered, repos)

        wrong_repos = list(repos)
        wrong_repos[-1] = "https://codeberg.org/owner/different"
        with self.assertRaises(PermissionError):
            service.paid_repos(session, wrong_repos)

    def test_paid_order_rejects_malformed_metadata(self) -> None:
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
                "pricing_rule": "every_fifth_free",
                "repo_count": "5",
                "paid_count": "4",
                "free_count": "1",
                "repo_digest": "a" * 64,
            },
            {
                "pubskill_product": "audit",
                "pricing_rule": "other",
                "repo_count": "5",
                "paid_count": "4",
                "free_count": "1",
                "repo_digest": "a" * 64,
            },
            {
                "pubskill_product": "audit",
                "pricing_rule": "every_fifth_free",
                "repo_count": "5",
                "paid_count": "5",
                "free_count": "0",
                "repo_digest": "a" * 64,
            },
            {
                "pubskill_product": "audit",
                "pricing_rule": "every_fifth_free",
                "repo_count": "5",
                "paid_count": "4",
                "free_count": "1",
                "repo_digest": "short",
            },
        )
        for metadata in bad_metadata:
            session = dict(base)
            session["metadata"] = metadata
            with self.subTest(metadata=metadata):
                with self.assertRaises((PermissionError, ValueError)):
                    service.paid_order(session)

    def test_operator_code_is_server_side_and_constant_time_comparable(self) -> None:
        with patch.dict(os.environ, {"PUBSKILL_OPERATOR_CODE": "secret-code"}, clear=False):
            self.assertTrue(service.operator_authorized("secret-code"))
            self.assertFalse(service.operator_authorized("wrong"))
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(service.operator_authorized("secret-code"))

    def test_checkout_form_uses_paid_quantity_and_digest(self) -> None:
        captured = {}

        def fake_stripe_api(path, form=None):
            captured["path"] = path
            captured["form"] = dict(form or [])
            return {"id": "cs_test", "url": "https://checkout.stripe.com/test"}

        repos = [f"https://github.com/owner/repo-{index}" for index in range(11)]
        with patch.object(service, "stripe_api", fake_stripe_api):
            session, pricing = service.create_checkout(repos)

        self.assertEqual(session["id"], "cs_test")
        self.assertEqual(pricing["repository_count"], 11)
        self.assertEqual(pricing["paid_count"], 9)
        self.assertEqual(pricing["free_count"], 2)
        self.assertEqual(pricing["amount_cents"], 4500)
        self.assertEqual(captured["path"], "checkout/sessions")
        self.assertEqual(captured["form"]["line_items[0][price]"], service.AUDIT_UNIT_PRICE_ID)
        self.assertEqual(captured["form"]["line_items[0][quantity]"], "9")
        self.assertEqual(captured["form"]["metadata[repo_count]"], "11")
        self.assertEqual(captured["form"]["metadata[paid_count]"], "9")
        self.assertEqual(captured["form"]["metadata[free_count]"], "2")
        self.assertEqual(captured["form"]["metadata[repo_digest]"], service.repo_digest(repos))
        self.assertFalse(any(key.startswith("metadata[repo_") and key != "metadata[repo_count]" and key != "metadata[repo_digest]" for key in captured["form"]))


if __name__ == "__main__":
    unittest.main()
