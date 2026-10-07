"""Build-time packaging for pubskill-lib.

The wheel carries the source-pinned vendored skill catalog under
`pubskill_lib/_skills` so the versioned API and MCP tools can resolve the
canonical skills when installed outside a source checkout. The copy is derived
from `.agents/skills` at build time; the repository's canonical-source CI gate
keeps that directory byte-identical to the pinned producer.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
SKILLS_SOURCE = ROOT / ".agents" / "skills"


class build_py_with_skills(build_py):
    def run(self) -> None:
        super().run()
        if not SKILLS_SOURCE.is_dir():
            raise RuntimeError(f"vendored skills root missing: {SKILLS_SOURCE}")
        destination = Path(self.build_lib) / "pubskill_lib" / "_skills"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(SKILLS_SOURCE, destination)


setup(cmdclass={"build_py": build_py_with_skills})
