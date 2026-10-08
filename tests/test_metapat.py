"""Phase D METAPAT adapter tests: exact pin, digest check, HMMM on incomplete
evidence, zero transfer flags, and enablement-gated MCP/HTTP exposure.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pubskill_lib import api, metapat_adapter, mcp_server

REPO = Path(__file__).resolve().parents[1]
METAPAT_REPO = REPO.parent / "metapat"
PIN = metapat_adapter.METAPAT_COMMIT


def _pin_available() -> bool:
    if not (METAPAT_REPO / ".git").is_dir():
        return False
    result = subprocess.run(
        ["git", "-C", str(METAPAT_REPO), "cat-file", "-t", PIN],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _add_worktree(commit: str | None) -> tuple[str, Path]:
    tmp = tempfile.mkdtemp(prefix="pubskill-metapat-test-")
    path = Path(tmp) / "checkout"
    command = ["git", "-C", str(METAPAT_REPO), "worktree", "add", "--detach", str(path)]
    if commit:
        command.append(commit)
    subprocess.run(command, check=True, capture_output=True, text=True)
    return tmp, path


def _remove_worktree(tmp: str, path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(METAPAT_REPO), "worktree", "remove", "--force", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(_pin_available(), "metapat repository or pinned commit unavailable")
class MetapatAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_pin, cls.pin_root = _add_worktree(PIN)
        cls.pin_env = {"PUBSKILL_METAPAT_ROOT": str(cls.pin_root)}
        cls.mismatch_tmp, cls.mismatch_root = _add_worktree(None)
        cls.mismatch_env = {"PUBSKILL_METAPAT_ROOT": str(cls.mismatch_root)}

    @classmethod
    def tearDownClass(cls) -> None:
        _remove_worktree(cls.tmp_pin, cls.pin_root)
        _remove_worktree(cls.mismatch_tmp, cls.mismatch_root)

    def _catalog_identity(self) -> dict:
        with mock.patch.dict(os.environ, self.pin_env):
            return metapat_adapter.metapat_catalog_identity()

    def _evidence(self, **overrides) -> dict:
        identity = self._catalog_identity()
        evidence = {
            "source_domain": "fixture:domain-a",
            "target_domain": "fixture:domain-b",
            "source_origin_id": "origin:a",
            "target_origin_id": "origin:b",
            "source_path_id": "path:a",
            "target_path_id": "path:b",
            "declared_invariants": ["fixture:ordered-relation"],
            "preserved_invariants": [],
            "mapping_complete": None,
            "replay_passed": None,
            "catalog_version": identity["catalog_version"],
            "catalog_digest": identity["catalog_digest"],
            "catalog_module_ids": identity["required_module_ids"],
            "ancestry_resolved": False,
            "unresolved": ["UCNS comparison evidence has not been supplied"],
        }
        evidence.update(overrides)
        return evidence

    def test_pin_mismatch_fails_closed(self):
        with mock.patch.dict(os.environ, self.mismatch_env):
            self.assertFalse(metapat_adapter.is_metapat_enabled())
            with self.assertRaises(metapat_adapter.MetapatUnavailable):
                metapat_adapter.classify_recurrence(self._evidence())

    def test_dirty_checkout_fails_closed(self):
        marker = self.pin_root / "uncommitted-review-edit.txt"
        marker.write_text("dirty", encoding="utf-8")
        try:
            with mock.patch.dict(os.environ, self.pin_env):
                self.assertFalse(metapat_adapter.is_metapat_enabled())
        finally:
            marker.unlink(missing_ok=True)

    def test_catalog_identity_exposes_pin_and_digest(self):
        identity = self._catalog_identity()
        self.assertEqual(identity["repository"], "The-Interdependency/metapat")
        self.assertEqual(identity["commit"], PIN)
        self.assertRegex(identity["catalog_digest"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(identity["required_module_ids"]), 4)

    def test_incomplete_evidence_returns_hmmm(self):
        with mock.patch.dict(os.environ, self.pin_env):
            decision = metapat_adapter.classify_recurrence(self._evidence())
        self.assertEqual(decision["outcome"], "HMMM")
        self.assertIsNone(decision["independent"])

    def test_zero_transfer_flags_are_enforced(self):
        with mock.patch.dict(os.environ, self.pin_env):
            decision = metapat_adapter.classify_recurrence(self._evidence())
        self.assertFalse(decision["semantic_transfer"])
        self.assertFalse(decision["proof_status_transfer"])
        self.assertFalse(decision["measurement_status_transfer"])

    def test_same_structure_requires_explicit_proof_identity(self):
        complete = self._evidence(
            preserved_invariants=["fixture:ordered-relation"],
            mapping_complete=True,
            replay_passed=True,
            ancestry_resolved=True,
            unresolved=[],
            equivalence_proof_id=None,
        )
        with mock.patch.dict(os.environ, self.pin_env):
            without_proof = metapat_adapter.classify_recurrence(complete)
            self.assertNotEqual(without_proof["outcome"], "SAME_STRUCTURE")
            with_proof = metapat_adapter.classify_recurrence(
                {**complete, "equivalence_proof_id": "proof:explicit-equivalence-v1"}
            )
            self.assertEqual(with_proof["outcome"], "SAME_STRUCTURE")

    def test_catalog_digest_mismatch_is_rejected(self):
        with mock.patch.dict(os.environ, self.pin_env):
            with self.assertRaises(metapat_adapter.MetapatUnavailable):
                metapat_adapter.classify_recurrence(
                    {**self._evidence(), "catalog_digest": "0" * 64}
                )

    def test_unknown_evidence_fields_are_rejected(self):
        with mock.patch.dict(os.environ, self.pin_env):
            with self.assertRaises(ValueError):
                metapat_adapter.classify_recurrence({**self._evidence(), "extra": 1})

    def test_v1_recurrence_envelope(self):
        with mock.patch.dict(os.environ, self.pin_env):
            response = api.v1_metapat_recurrence(self._evidence())
        self.assertEqual(response["route"], "metapat.recurrence")
        self.assertEqual(response["decision"]["outcome"], "HMMM")

    def test_mcp_tool_listed_only_when_enabled(self):
        with mock.patch.dict(os.environ, self.pin_env):
            enabled_names = {tool["name"] for tool in mcp_server.tool_schemas()}
            self.assertIn("pubskill_classify_recurrence", enabled_names)
            called = mcp_server.handle_jsonrpc({
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "pubskill_classify_recurrence", "arguments": {"evidence": self._evidence()}},
            })
            text = json.loads(called["result"]["content"][0]["text"])
            self.assertEqual(text["decision"]["outcome"], "HMMM")
        with mock.patch.dict(os.environ, self.mismatch_env):
            disabled_names = {tool["name"] for tool in mcp_server.tool_schemas()}
            self.assertNotIn("pubskill_classify_recurrence", disabled_names)


if __name__ == "__main__":
    unittest.main()
