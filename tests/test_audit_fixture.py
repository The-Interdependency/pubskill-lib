import json
import unittest
from pathlib import Path

from pubskill_lib import audit, schema

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "examples" / "neglected-repo"
EXPECTED = FIXTURE / "expected-findings.json"


def _key(document):
    return [(f["id"], f["class"], f["surface"]) for f in document["findings"]]


class AuditFixtureTests(unittest.TestCase):
    def test_fixture_findings_match_expected_on_id_class_surface(self):
        document = audit.audit_path(FIXTURE, audit._read_source_pin())
        schema.validate_document(document)
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_key(document), _key(expected))

    def test_fixture_has_at_least_three_evidenced_defects(self):
        document = audit.audit_path(FIXTURE, audit._read_source_pin())
        defects = [f for f in document["findings"] if f["class"] == "defect"]
        self.assertGreaterEqual(len(defects), 3)
        for finding in defects:
            self.assertTrue(finding["evidence"])
            self.assertFalse(finding["verified"])

    def test_fixture_covers_docs_ci_and_deps_surfaces(self):
        document = audit.audit_path(FIXTURE, audit._read_source_pin())
        surfaces = {f["surface"] for f in document["findings"]}
        self.assertTrue({"docs", "ci", "deps"}.issubset(surfaces))

    def test_fixture_identity_is_unresolved_hmmm(self):
        document = audit.audit_path(FIXTURE, audit._read_source_pin())
        self.assertEqual(document["target"]["commit"], "hmmm")
        self.assertEqual(document["target"]["remote"], "hmmm")
        self.assertTrue(
            any("identity" in entry for entry in document["hmmm"])
        )


if __name__ == "__main__":
    unittest.main()
