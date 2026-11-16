"""Imported Apache-2.0 skills must travel with their attribution files."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTED = ("sql-queries", "statistical-analysis", "explore-data", "validate-data")


class ImportedAttributionTests(unittest.TestCase):
    def test_attribution_and_apache_license_are_present(self) -> None:
        attribution = (ROOT / "ATTRIBUTION.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSES" / "Apache-2.0.txt").read_text(encoding="utf-8")
        self.assertIn("anthropics/knowledge-work-plugins", attribution)
        self.assertIn("Apache-2.0", attribution)
        self.assertIn("Apache License", license_text)
        for name in IMPORTED:
            self.assertIn(f"{name}/", attribution)
            skill = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("See `ATTRIBUTION.md` at repo root.", skill)
            self.assertIn("Apache-2.0", skill)


if __name__ == "__main__":
    unittest.main()
