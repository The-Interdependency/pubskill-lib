"""Build-time helpers shared by setup.py and tests."""
from __future__ import annotations


def ignore_skill_runtime(directory: str, names: list[str]) -> set[str]:
    """Exclude generated caches and installed reader runtimes from packaging."""
    ignored = set()
    for name in names:
        if name == "__pycache__" or name == "node_modules" or name.endswith(".pyc"):
            ignored.add(name)
    return ignored
