from __future__ import annotations

import unittest

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

    def test_paid_repo_binds_payment_product_amount_and_repository(self) -> None:
        session = {
            "payment_status": "paid",
            "payment_link": service.PAYMENT_LINK_ID,
            "currency": "usd",
            "amount_total": service.PRICE_CENTS,
            "custom_fields": [
                {
                    "key": "githubrepo",
                    "type": "text",
                    "text": {"value": "https://codeberg.org/owner/repo"},
                }
            ],
        }
        self.assertEqual(
            service.paid_repo(session),
            "https://codeberg.org/owner/repo",
        )

        for field, value in (
            ("payment_status", "unpaid"),
            ("payment_link", "plink_other"),
            ("currency", "eur"),
            ("amount_total", service.PRICE_CENTS + 1),
        ):
            altered = dict(session)
            altered[field] = value
            with self.subTest(field=field):
                with self.assertRaises(PermissionError):
                    service.paid_repo(altered)

    def test_paid_repo_rejects_missing_or_invalid_checkout_repository(self) -> None:
        base = {
            "payment_status": "paid",
            "payment_link": service.PAYMENT_LINK_ID,
            "currency": "usd",
            "amount_total": service.PRICE_CENTS,
        }
        for custom_fields in (
            [],
            [{"key": "other", "type": "text", "text": {"value": "https://github.com/a/b"}}],
            [{"key": "githubrepo", "type": "text", "text": {"value": "https://example.com/a/b"}}],
        ):
            session = dict(base)
            session["custom_fields"] = custom_fields
            with self.subTest(custom_fields=custom_fields):
                with self.assertRaises(ValueError):
                    service.paid_repo(session)


if __name__ == "__main__":
    unittest.main()
