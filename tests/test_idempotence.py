import tempfile
import unittest
from pathlib import Path

from pubskill_lib import evidence, examine, narrative


class ExaminerIdempotenceTests(unittest.TestCase):
    def test_generated_metadata_does_not_stale_its_own_narrative(self):
        class FakeProvider:
            name = "fake"
            model = "model-1"

            def chat(self, system, user):
                return "Prints a greeting."

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool.py"
            source.write_text(
                "#!/usr/bin/env python3\n"
                "# -*- coding: utf-8 -*-\n"
                "print('hi')\n",
                encoding="utf-8",
            )

            first_evidence = evidence.inventory(root)
            _, first_report = examine._apply(root, first_evidence, [FakeProvider()], True)
            first_output = source.read_text(encoding="utf-8")
            self.assertTrue(first_report["changed"])

            second_evidence = evidence.inventory(root)
            self.assertEqual(1, len(second_evidence))
            entry = second_evidence[0].narrative_entries[0]
            self.assertFalse(narrative.is_stale(entry, second_evidence[0].sha256))

            _, second_report = examine._apply(root, second_evidence, [], False)
            second_output = source.read_text(encoding="utf-8")
            self.assertEqual(first_output, second_output)
            self.assertEqual([], second_report["changed"])

    def test_source_hash_excludes_generated_narrative_and_ratios(self):
        plain = "print('hi')\n"
        decorated = (
            "# ratios: loc_comments=1:0 imports_exports=0:0 calls_definitions=1:0\n"
            "# === NARRATIVE ===\n"
            "# id: examiner_x\n"
            "# summary: Prints hi.\n"
            "# evidence_sha256: x\n"
            "# === END NARRATIVE ===\n"
            "print('hi')\n"
            "# ratios: loc_comments=1:0 imports_exports=0:0 calls_definitions=1:0\n"
        )
        self.assertEqual(
            evidence.source_text(plain, "#"),
            evidence.source_text(decorated, "#"),
        )


if __name__ == "__main__":
    unittest.main()
