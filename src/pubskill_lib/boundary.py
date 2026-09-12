"""Repository boundary enforcement for the examiner.

The tool runs only inside the repository that contains it. Every path the
tool reads or writes is resolved and asserted to stay inside the resolved
repository root. Symlinked files are skipped rather than followed, so a
symlink cannot smuggle a path outside the boundary.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_SKIP = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", ".nuxt", "target", ".pytest_cache", ".mypy_cache",
    ".tox", ".agents",
}


class BoundaryError(PermissionError):
    """Raised when a path escapes the repository boundary."""


def repo_root(start: str | Path | None = None) -> Path:
    """Resolve the repository root.

    Uses git top-level when available, otherwise the start directory itself.
    """
    start = Path(start if start is not None else os.getcwd()).resolve()
    if not start.is_dir():
        raise NotADirectoryError(f"not a directory: {start}")
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return start


def assert_inside(root: Path, path: Path) -> Path:
    """Return ``path`` resolved, or raise if it escapes ``root``."""
    root = Path(root).resolve()
    path = Path(path).resolve()
    try:
        inside = path.is_relative_to(root)
    except AttributeError:  # pragma: no cover - Python < 3.9
        inside = str(path) == str(root) or str(path).startswith(str(root) + os.sep)
    if not inside:
        raise BoundaryError(f"path escapes repository boundary: {path}")
    return path


def iter_files(root: Path, skip: set[str] | None = None) -> list[Path]:
    """Return regular, non-symlink files inside ``root``, sorted."""
    root = Path(root).resolve()
    skip = set(skip if skip is not None else DEFAULT_SKIP)
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip and not d.startswith(".examiner-originals-"))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            try:
                if path.is_symlink():
                    continue
            except OSError:
                continue
            found.append(path)
    return sorted(found)
