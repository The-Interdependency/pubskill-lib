"""Run the public char-compress core: python -m unittest discover -s tests.

The skill is a declared redacted copy of skill-lib's char-compress (see
docs/derived-copies.json). These tests run its preservation checker and
fixtures, bind the published bytes to the derived-copy record, and keep
org-specific material out of the public copy. Producer-side hashes are checked
against the trusted skill-lib checkout by the canonical-source CI job.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "char-compress"
CHECKER = SKILL / "char_compress_check.py"
RECORD = ROOT / "docs" / "derived-copies.json"
DENYLIST = ROOT / "templates" / "leak-denylist.json"

# Always enforced, even before the template leak denylist exists on this branch.
CORE_DENY = [
    ("interdependency", "substring"), ("ucns", "substring"), ("edcm", "substring"),
    ("hovel", "substring"), ("erin", "token"), ("a0", "token"), ("skill-lib", "token"),
    ("twic", "token"), ("unit circle number system", "substring"),
]


def run_checker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECKER), *args], capture_output=True, text=True)


def deny_terms():
    terms = list(CORE_DENY)
    if DENYLIST.is_file():
        terms += [(e["term"], e["match"]) for e in json.loads(DENYLIST.read_text())["entries"]]
    return terms


def leaks(text: str):
    lowered = text.lower()
    found = []
    for term, mode in deny_terms():
        term = term.lower()
        if mode == "substring":
            hit = term in lowered
        else:
            hit = re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", lowered) is not None
        if hit:
            found.append(term)
    return found


class CharCompressCheckerTests(unittest.TestCase):
    def test_fixtures_pass(self):
        result = run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("char-compress fixtures: pass (8 checked)", result.stdout)

    def test_json_result(self):
        result = run_checker("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual((data["status"], data["fixtures"], data["failures"]), ("pass", 8, []))

    def test_dropped_negation_and_forbidden_claim_fail(self):
        fixtures = json.loads((SKILL / "fixtures.json").read_text())
        by_id = {item["id"]: item for item in fixtures["fixtures"]}
        by_id["negation_preserved"]["text"] = "The scheduler is a supervisor."
        by_id["status_preserved"]["forbid_anywhere"] = ["EXPERIMENTAL"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.json"
            path.write_text(json.dumps(fixtures))
            result = run_checker("--fixtures", str(path), "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        failed = {item["fixture_id"] for item in json.loads(result.stdout)["failures"]}
        self.assertEqual(failed, {"negation_preserved", "status_preserved"})

    def test_minimum_fixture_set_matches_skill(self):
        ids = [item["id"] for item in json.loads((SKILL / "fixtures.json").read_text())["fixtures"]]
        text = (SKILL / "SKILL.md").read_text()
        minimum = text.split("Minimum fixture set for an implementation:", 1)[1]
        for fixture_id in ids:
            self.assertIn(fixture_id, minimum)


class CharCompressDerivedCopyTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(RECORD.read_text())
        self.copy = next(item for item in self.record["copies"] if item["name"] == "char-compress")

    def test_record_is_bound_to_source_pin(self):
        source = json.loads((ROOT / "src/pubskill_lib/_source.json").read_text())
        self.assertEqual(self.record["schema"], "pubskill-lib.derived-copies")
        self.assertEqual(self.record["source_commit"], source["commit"])
        self.assertEqual(self.copy["relation"], "redacted")
        self.assertTrue(self.copy["removed"])
        self.assertTrue(self.copy["hmmm"])

    def test_published_bytes_match_record_and_no_unrecorded_files(self):
        recorded = set()
        for item in self.copy["files"]:
            self.assertRegex(item["source_sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(item["relation"], {"exact", "redacted"})
            digest = hashlib.sha256((ROOT / item["consumer"]).read_bytes()).hexdigest()
            self.assertEqual(digest, item["consumer_sha256"], item["consumer"])
            if item["relation"] == "exact":
                self.assertEqual(item["source_sha256"], item["consumer_sha256"], item["consumer"])
            recorded.add(item["consumer"])
        present = {str(path.relative_to(ROOT)) for path in SKILL.rglob("*")
                   if path.is_file() and "__pycache__" not in path.parts}
        self.assertEqual(present, recorded)

    def test_public_copy_has_no_org_terms(self):
        for path in sorted(SKILL.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                self.assertEqual(leaks(path.read_text()), [], str(path.relative_to(ROOT)))

    def test_removed_sections_stay_removed(self):
        text = (SKILL / "SKILL.md").read_text()
        for heading in ("## Repository placement", "### Relation to", "## Optional local text-stack notation",
                        "Optional historical extension", "text_stack:", "local_notation:"):
            self.assertNotIn(heading, text)

    def test_preservation_guards_survive_redaction(self):
        text = (SKILL / "SKILL.md").read_text()
        for guard in ("## Channels", "## Suppression sort", "## Compression procedure",
                      "## Output shape for compressed handoffs", "## Skill-writing use",
                      "## Falsifiability tests", "## Security note", "## Completion criteria",
                      "## Anti-patterns", "## hmmm", "Freeze dangerous bones", "Reconstruct and compare",
                      "Carry hmmm", "lost recurrence order", "dropped negation", "changed proof/status label",
                      "Compression is not opacity"):
            self.assertIn(guard, text)


if __name__ == "__main__":
    unittest.main()
