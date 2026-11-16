from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llms.build import collect, generate, parse_text


class LlmsBuildTest(unittest.TestCase):
    def test_parse_llms_block_allows_hyphenated_key_definitions(self) -> None:
        text = """# === LLMS ===
# id: key_definitions
#   msdmd: Module Self-Declared Metadata in Markdown
#   char-compress: Character-based context compression
#   llms-build: Root llms.txt generation
# === END LLMS ===
"""
        entries = parse_text(text, "#")

        self.assertEqual(1, len(entries))
        self.assertEqual("key_definitions", entries[0].id)
        self.assertEqual("Module Self-Declared Metadata in Markdown", entries[0].fields["msdmd"])
        self.assertEqual("Character-based context compression", entries[0].fields["char-compress"])
        self.assertEqual("Root llms.txt generation", entries[0].fields["llms-build"])

    def test_markdown_fenced_code_examples_are_ignored(self) -> None:
        text = """```markdown
# === LLMS ===
# id: project_overview
#   content: example only
# === END LLMS ===
```

# === LLMS ===
# id: project_overview
#   content: real declaration
# === END LLMS ===
"""
        entries = parse_text(text, "#", source=Path("README.md"))

        self.assertEqual(1, len(entries))
        self.assertEqual("real declaration", entries[0].fields["content"])

    def test_generate_uses_hmmm_for_missing_sections(self) -> None:
        generated = generate([], repo_name="demo")

        self.assertIn("# LLM Instructions for demo", generated)
        self.assertIn("## Project Overview\nhmmm", generated)
        self.assertIn("- **hmmm** = hmmm", generated)
        self.assertIn("## Architecture Summary\nhmmm", generated)
        self.assertIn("## How to Use This Repo with LLMs / Agents\nhmmm", generated)

    def test_native_only_input_retains_uncertainty_and_source_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("Native instructions remain here.\n")
            entries = collect(root)
            generated = generate(entries, repo_name="native-only")

        self.assertEqual([], entries)
        self.assertIn("hmmm", generated)
        self.assertIn("Owning source declarations remain authoritative", generated)
        self.assertIn("omission here does not establish absence", generated)
        self.assertNotIn("single source of truth", generated)
        self.assertNotIn("does not exist in this repository", generated)

    def test_collect_and_generate_from_repo_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module.py").write_text(
                """# === LLMS ===
# id: project_overview
#   content: Demo repo.
# id: key_definitions
#   demo: exact definition
# id: architecture_summary
#   content: - One module.
# id: usage_rules
#   content: - Read source first.
# === END LLMS ===
""",
                encoding="utf-8",
            )

            generated = generate(collect(root), repo_name="demo")

        self.assertIn("Demo repo.", generated)
        self.assertIn("- **demo** = exact definition", generated)
        self.assertIn("- One module.", generated)
        self.assertIn("- Read source first.", generated)


if __name__ == "__main__":
    unittest.main()
