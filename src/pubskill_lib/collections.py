"""Schema-2 MSDMD collection through the canonical vendored implementation.

The collector is invoked as the vendored ``msdmd.collect`` module over a
bounded local checkout. It is never copied or rewritten here; missing optional
reader runtimes surface as unsupported-reader diagnostics from the canonical
implementation, never as empty success.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .identity import skills_root

DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_COLLECT_TIMEOUT_SECONDS = 180
MSDMD_SCHEMA = "the-interdependency.msdmd-collection"
MSDMD_SCHEMA_VERSION = "2.0.0"


class CollectionError(RuntimeError):
    """Schema-2 collection produced errors or could not be validated."""


@dataclass(frozen=True)
class CollectionResult:
    collection: dict
    command: list[str]
    returncode: int
    stderr: str


def runtime_status() -> dict:
    """Preflight: which declared reader runtimes are present in this build."""
    python_runtimes = {}
    for module_name in (
        "yaml",
        "docstring_parser",
        "tree_sitter",
        "tree_sitter_rust",
        "tree_sitter_java",
        "tree_sitter_c",
        "tree_sitter_cpp",
    ):
        python_runtimes[module_name] = importlib.util.find_spec(module_name) is not None

    node = shutil.which("node")
    tsc = None
    if node:
        candidate = skills_root() / "msdmd" / "node_modules" / "typescript" / "bin" / "tsc"
        tsc = str(candidate) if candidate.is_file() else None

    return {
        "python_runtimes": python_runtimes,
        "node": node,
        "typescript_tsc": tsc,
        "declared": {
            "python": sorted(python_runtimes),
            "node_typescript": "msdmd/package.json",
        },
        "missing": [name for name, present in python_runtimes.items() if not present],
    }


def _resolve_git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else "hmmm"
    except (OSError, subprocess.TimeoutExpired):
        return "hmmm"


def collect_metadata(
    root: Path,
    repo: str,
    *,
    revision: str | None = None,
    strict: bool = True,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    require_sources: tuple[str, ...] = (),
    require_facts: tuple[str, ...] = (),
    timeout_seconds: int = DEFAULT_COLLECT_TIMEOUT_SECONDS,
) -> CollectionResult:
    """Run the canonical schema-2 collector over a local checkout.

    The inspected repository is never imported, executed, or installed by this
    function; the canonical collector reads source bytes only.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    if not repo or any(char in repo for char in ("\x00", "\n")):
        raise ValueError("invalid repository slug")

    skills = skills_root()
    if not (skills / "msdmd" / "collect.py").is_file():
        raise RuntimeError(f"canonical msdmd collector missing under {skills}")

    env = dict(os.environ)
    pythonpath = str(skills)
    if env.get("PYTHONPATH"):
        pythonpath += os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    command = [
        sys.executable,
        "-m",
        "msdmd.collect",
        "--root",
        str(root),
        "--repo",
        repo,
        "--json",
        "--max-file-bytes",
        str(max_file_bytes),
    ]
    detected_commit = _resolve_git_commit(root)
    if revision:
        command += ["--source-commit", revision]
    elif detected_commit != "hmmm":
        command += ["--source-commit", detected_commit]
    else:
        # No git identity available: bind facts to the exact source bytes
        # instead of a commit. The canonical collector forbids selecting both.
        command += ["--snapshot-identity"]
    for pattern in require_sources:
        command += ["--require-source", pattern]
    for requirement in require_facts:
        command += ["--require-fact", requirement]
    if strict:
        command.append("--strict")

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise CollectionError(f"collection timed out after {timeout_seconds}s") from error
    except OSError as error:
        raise CollectionError(f"collector could not start: {error}") from error

    if completed.returncode not in (0, 2):
        raise CollectionError(
            f"collector exited {completed.returncode}: {completed.stderr.strip()[:4000]}"
        )

    try:
        collection = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise CollectionError(
            f"collector emitted invalid JSON: {error}; stderr: {completed.stderr.strip()[:2000]}"
        ) from error

    if collection.get("schema") != MSDMD_SCHEMA:
        raise CollectionError(f"unexpected collection schema: {collection.get('schema')}")
    if collection.get("schema_version") != MSDMD_SCHEMA_VERSION:
        raise CollectionError(
            f"unexpected collection schema version: {collection.get('schema_version')}"
        )

    result = CollectionResult(
        collection=collection,
        command=command,
        returncode=completed.returncode,
        stderr=completed.stderr,
    )
    if strict and completed.returncode == 2:
        errors = [
            item
            for item in collection.get("diagnostics", [])
            if item.get("severity") == "error"
        ]
        raise CollectionError(
            "strict collection failed with error diagnostics: "
            + json.dumps(errors, ensure_ascii=False)[:4000]
        )
    return result
