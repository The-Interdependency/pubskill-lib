"""Build-time packaging for pubskill-lib.

The wheel carries the source-pinned vendored skill catalog under
`pubskill_lib/_skills` so the versioned API and MCP tools can resolve the
canonical skills when installed outside a source checkout. The copy is derived
from `.agents/skills` at build time; the repository's canonical-source CI gate
keeps that directory byte-identical to the pinned producer. The build also
records the consumer source identity in `pubskill_lib/_build.json` so an
installed artifact reports the exact deployment commit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
SKILLS_SOURCE = ROOT / ".agents" / "skills"
sys.path.insert(0, str(ROOT / "src"))
from pubskill_lib.packaging_helpers import ignore_skill_runtime  # noqa: E402


def _consumer_commit() -> str:
    source_identity = ROOT / "src" / "pubskill_lib" / "_build.json"
    if source_identity.is_file():
        try:
            recorded = json.loads(source_identity.read_text(encoding="utf-8"))
            commit = recorded.get("consumer_commit")
            if isinstance(commit, str) and commit:
                return commit
        except (OSError, json.JSONDecodeError):
            pass
    override = os.environ.get("PUBSKILL_CONSUMER_COMMIT")
    if override:
        return override
    try:
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0 or status.stdout.strip():
            return "hmmm"
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else "hmmm"
    except OSError:
        return "hmmm"


def _ignore_skill_runtime(directory: str, names: list[str]) -> set[str]:
    """Exclude generated caches and installed reader runtimes from the wheel."""
    return ignore_skill_runtime(directory, names)


class build_py_with_skills(build_py):
    def run(self) -> None:
        super().run()
        if not SKILLS_SOURCE.is_dir():
            raise RuntimeError(f"vendored skills root missing: {SKILLS_SOURCE}")
        destination = Path(self.build_lib) / "pubskill_lib" / "_skills"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(SKILLS_SOURCE, destination, ignore=_ignore_skill_runtime)
        build_identity = Path(self.build_lib) / "pubskill_lib" / "_build.json"
        build_identity.write_text(
            json.dumps(
                {
                    "schema": "pubskill-lib.build",
                    "version": 1,
                    "consumer_commit": _consumer_commit(),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


setup(cmdclass={"build_py": build_py_with_skills})
