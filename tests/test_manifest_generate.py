"""Exercise the vendored manifest generator contract on a temporary fixture."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / ".agents" / "skills" / "manifest" / "generate.py"


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _fixture(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "fixture-pkg"
version = "0.0.1"
description = "Temporary manifest fixture"
requires-python = ">=3.11"
license = "MPL-2.0"
""",
        encoding="utf-8",
    )
    (root / "src").mkdir()


class ManifestGenerateTests(unittest.TestCase):
    def test_print_write_check_and_stale_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)

            printed = _run(["--root", str(root), "--print"], cwd=root)
            self.assertEqual(printed.returncode, 0, printed.stdout + printed.stderr)
            self.assertIn("<!-- BEGIN GENERATED:manifest -->", printed.stdout)
            self.assertIn("`fixture-pkg`", printed.stdout)
            self.assertIn("`0.0.1`", printed.stdout)
            self.assertIn("hmmm", printed.stdout)  # absent authors/repository/status

            missing = _run(["--root", str(root), "--check"], cwd=root)
            self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)

            written = _run(["--root", str(root), "--write"], cwd=root)
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("<!-- BEGIN GENERATED:manifest -->", claude)
            self.assertIn("`fixture-pkg`", claude)

            current = _run(["--root", str(root), "--check"], cwd=root)
            self.assertEqual(current.returncode, 0, current.stdout + current.stderr)

            again = _run(["--root", str(root), "--write"], cwd=root)
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            self.assertEqual(claude, (root / "CLAUDE.md").read_text(encoding="utf-8"))

            (root / "pyproject.toml").write_text(
                (root / "pyproject.toml").read_text(encoding="utf-8").replace("0.0.1", "0.0.2"),
                encoding="utf-8",
            )
            stale = _run(["--root", str(root), "--check"], cwd=root)
            self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)


if __name__ == "__main__":
    unittest.main()
