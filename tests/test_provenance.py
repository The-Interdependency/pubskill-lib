import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PIN_RE = re.compile(r"`([0-9a-f]{40})`")


class PublicationProvenanceTests(unittest.TestCase):
    def test_source_pin_matches_vendored_skill_manifest(self):
        source = (REPO / "SOURCE.md").read_text(encoding="utf-8")
        vendored = (REPO / ".agents" / "skills" / "README.md").read_text(encoding="utf-8")
        source_pin = PIN_RE.search(source)
        vendored_pin = PIN_RE.search(vendored)
        self.assertIsNotNone(source_pin)
        self.assertIsNotNone(vendored_pin)
        self.assertEqual(source_pin.group(1), vendored_pin.group(1))

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
