import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PIN_RE = re.compile(r"`([0-9a-f]{40})`")


def _source_pin() -> str:
    source = (REPO / "SOURCE.md").read_text(encoding="utf-8")
    match = PIN_RE.search(source)
    if match is None:
        raise AssertionError("SOURCE.md has no pinned SHA")
    return match.group(1)


class PublicationProvenanceTests(unittest.TestCase):
    def test_source_pin_matches_vendored_skill_manifest(self):
        vendored = (REPO / ".agents" / "skills" / "README.md").read_text(encoding="utf-8")
        vendored_pin = PIN_RE.search(vendored)
        self.assertIsNotNone(vendored_pin)
        self.assertEqual(_source_pin(), vendored_pin.group(1))

    def test_fixture_source_pin_matches_publication_pin(self):
        expected = json.loads(
            (REPO / "examples" / "neglected-repo" / "expected-findings.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(_source_pin(), expected["source_pin"])

    def test_local_secret_files_are_ignored(self):
        ignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env", ignore)
        self.assertIn(".env.*", ignore)
        self.assertIn("*.egg-info/", ignore)

    def test_readme_does_not_claim_unpublished_v020_tag(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("release pending", readme)
        self.assertNotIn("**shipped** — `v0.2`", readme)


if __name__ == "__main__":
    unittest.main()
