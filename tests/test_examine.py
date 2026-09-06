import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pubskill_lib import assemble, boundary, evidence, msdmd_writer, narrative, ratios

FIXTURE = Path(__file__).resolve().parents[0] / "fixtures" / "mixed-repo"


class BoundaryTests(unittest.TestCase):
    def test_assert_inside_rejects_escape(self):
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(boundary.BoundaryError):
            boundary.assert_inside(root, Path("/etc/passwd"))


class RatiosWriterTests(unittest.TestCase):
    def test_place_ratios_keeps_shebang_first(self):
        text = "#!/usr/bin/env python3\nprint('hi')\n"
        new, changed = ratios.place_ratios(text, "#", {"loc_comments": "1:0", "imports_exports": "0:0", "calls_definitions": "1:0"})
        lines = new.splitlines()
        self.assertTrue(changed)
        self.assertTrue(lines[0].startswith("#!"))
        self.assertTrue(lines[1].startswith("# ratios:"))
        self.assertTrue(lines[-1].startswith("# ratios:"))

    def test_place_ratios_repairs_ratios_above_shebang(self):
        text = "# ratios: loc_comments=1:0 imports_exports=0:0 calls_definitions=0:0\n#!/bin/sh\necho hi\n"
        new, _ = ratios.place_ratios(text, "#", {"loc_comments": "1:0", "imports_exports": "0:0", "calls_definitions": "0:0"})
        lines = new.splitlines()
        self.assertTrue(lines[0].startswith("#!"))
        self.assertTrue(lines[1].startswith("# ratios:"))

    def test_compute_python_counts_code_and_comments(self):
        text = '"""doc"""\nimport os\n\ndef f():\n    return os.getcwd()\n'
        values = ratios.compute_python(text, "#")
        code, comment = values["loc_comments"].split(":")
        self.assertGreaterEqual(int(code), 3)
        self.assertGreaterEqual(int(comment), 1)


class MsdmdWriterTests(unittest.TestCase):
    def test_upsert_narrative_keeps_shebang_and_ratios(self):
        text = (
            "#!/usr/bin/env python3\n"
            "# ratios: loc_comments=1:0 imports_exports=0:0 calls_definitions=0:0\n"
            "print('hi')\n"
            "# ratios: loc_comments=1:0 imports_exports=0:0 calls_definitions=0:0\n"
        )
        entry = {"id": "examiner_abc", "summary": "Prints hi.", "evidence_sha256": "abc", "model": "none", "provider": "none", "generated_at": "now", "stale": "false"}
        new, changed = msdmd_writer.upsert_narrative(text, "#", entry)
        lines = new.splitlines()
        self.assertTrue(changed)
        self.assertEqual(lines[0], "#!/usr/bin/env python3")
        self.assertTrue(lines[1].startswith("# ratios:"))
        self.assertTrue(lines[2].startswith("# === NARRATIVE ==="))


class NarrativeTests(unittest.TestCase):
    def test_is_stale_detects_hash_mismatch(self):
        entry = {"evidence_sha256": "aaa"}
        self.assertTrue(narrative.is_stale(entry, "bbb"))
        self.assertFalse(narrative.is_stale(entry, "aaa"))


class AssembleTests(unittest.TestCase):
    def test_render_marks_stale_and_lists_gaps(self):
        ev = evidence.FileEvidence(path="a/tool.py", language="py", marker="#", sha256="aaa")
        docs = assemble.render_markdown(Path("/tmp/repo"), [ev], {"a/tool.py": {"summary": "s", "evidence_sha256": "bbb"}})
        self.assertIn("stale", docs)
        self.assertIn("Part —", docs)


class ExamineCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(FIXTURE, self.root)
        (self.root / "tool.py").chmod(0o755)
        (self.root / "run.sh").chmod(0o755)
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *extra):
        return subprocess.run(
            [sys.executable, "-m", "pubskill_lib.examine", "--repo", str(self.root), *extra],
            capture_output=True, text=True, cwd=str(self.root),
        )

    def test_dry_run_reports_without_writing(self):
        before = (self.root / "tool.py").read_text()
        result = self._run("--json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, (self.root / "tool.py").read_text())

    def test_apply_writes_ratios_and_assembles_docs(self):
        result = self._run("--apply", "--out", "docs/examiner")
        self.assertEqual(0, result.returncode, result.stderr)

        tool = (self.root / "tool.py").read_text().splitlines()
        self.assertTrue(tool[0].startswith("#!"))
        self.assertTrue(tool[1].startswith("# ratios: loc_comments="))
        self.assertTrue(tool[-1].startswith("# ratios:"))

        shell = (self.root / "run.sh").read_text().splitlines()
        self.assertTrue(shell[0].startswith("#!"))
        self.assertTrue(shell[1].startswith("# ratios: loc_comments=hmmm"))

        ts = (self.root / "lib" / "util.ts").read_text().splitlines()
        self.assertTrue(ts[0].startswith("// ratios: loc_comments=hmmm"))

        self.assertEqual((self.root / "tool.py").stat().st_mode & 0o111, 0o111)
        self.assertEqual((self.root / "run.sh").stat().st_mode & 0o111, 0o111)

        notes = (self.root / "notes.md").read_text()
        self.assertNotIn("ratios:", notes)

        volume = self.root / "docs" / "examiner" / "EXAMINER.md"
        self.assertTrue(volume.exists())
        text = volume.read_text()
        self.assertIn("no narrative generated", text)
        self.assertIn("unsupported language", text)


if __name__ == "__main__":
    unittest.main()
