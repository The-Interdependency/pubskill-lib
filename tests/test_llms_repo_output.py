"""The committed llms.txt must match the shipped runner for repo name pubskill-lib."""
from __future__ import annotations

import unittest
from pathlib import Path

from llms.build import collect, generate

ROOT = Path(__file__).resolve().parents[1]


class PubskillLlmsOutputTests(unittest.TestCase):
    def test_committed_llms_txt_matches_generated_output_for_repo_name(self) -> None:
        committed = (ROOT / "llms.txt").read_text(encoding="utf-8")
        generated = generate(collect(ROOT), repo_name="pubskill-lib")
        self.assertEqual(committed, generated)
        self.assertIn("# LLM Instructions for pubskill-lib", committed)
        self.assertIn("Public distribution of skill-lib", committed)


if __name__ == "__main__":
    unittest.main()
