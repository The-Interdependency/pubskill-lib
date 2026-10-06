"""Bounded public-repository acquisition.

The service clones supported public HTTPS repositories into an isolated
temporary worktree, resolves an immutable commit, and deletes the worktree
after the receipt is built. Target code is never installed, executed, or
instructed; git hooks, credential helpers, LFS smudging and submodule recursion
are disabled before any fetch.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

ALLOWED_GIT_HOSTS = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "codeberg.org",
    "git.sr.ht",
}

DEFAULT_LIMITS = {
    "request_bytes": 1024 * 1024,
    "fetch_timeout_seconds": 120,
    "checkout_timeout_seconds": 60,
    "max_repo_bytes": 50 * 1024 * 1024,
    "max_file_count": 20000,
    "max_per_file_bytes": 2 * 1024 * 1024,
    "max_collection_output_chars": 8 * 1024 * 1024,
}

_GIT_SAFE_CONFIG = [
    "-c",
    "credential.helper=",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "filter.lfs.smudge=",
    "-c",
    "filter.lfs.required=false",
    "-c",
    "protocol.ext.allow=never",
    "-c",
    "protocol.file.allow=never",
    "-c",
    "http.followRedirects=false",
]


class AcquisitionError(RuntimeError):
    """Repository acquisition was rejected or failed."""


@dataclass(frozen=True)
class AcquisitionResult:
    path: Path
    repo_url: str
    requested_revision: str | None
    resolved_commit: str
    duration_seconds: float
    limits: dict


def valid_repo_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    parts = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_GIT_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
        and 2 <= len(parts) <= 3
        and all(part and part not in (".", "..") and ".." not in part for part in parts)
        and not any(char in value for char in ("\x00", "\n", "\r"))
    )


def _repo_size_bytes(root: Path) -> tuple[int, int]:
    total = 0
    count = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            count += 1
            total += path.stat().st_size
    return total, count


@contextmanager
def acquire_repository(
    repo_url: str,
    *,
    revision: str | None = None,
    limits: dict | None = None,
) -> Iterator[AcquisitionResult]:
    """Clone one allowed public repository into an isolated temporary worktree.

    The worktree is deleted when the context exits; callers must build their
    receipt (and any collection) inside the ``with`` block.
    """
    repo_url = str(repo_url or "").strip()
    if not valid_repo_url(repo_url):
        raise AcquisitionError("supported public HTTPS Git repository required")
    if revision is not None and (
        not isinstance(revision, str)
        or not revision.strip()
        or any(char in revision for char in ("\x00", "\n", "\r", " ", "\t"))
    ):
        raise AcquisitionError("invalid revision")
    effective_limits = dict(DEFAULT_LIMITS)
    if limits:
        effective_limits.update(limits)

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="pubskill-acquire-") as tempdir:
        try:
            target = Path(tempdir) / "repo"
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            base = ["git"] + _GIT_SAFE_CONFIG

            subprocess.run(
                base + ["init", str(target)],
                check=True,
                capture_output=True,
                timeout=effective_limits["checkout_timeout_seconds"],
                env=env,
            )
            subprocess.run(
                base + ["-C", str(target), "remote", "add", "origin", repo_url],
                check=True,
                capture_output=True,
                timeout=effective_limits["checkout_timeout_seconds"],
                env=env,
            )
            fetch_ref = revision.strip() if revision else "HEAD"
            subprocess.run(
                base + ["-C", str(target), "fetch", "--depth=1", "origin", fetch_ref],
                check=True,
                capture_output=True,
                timeout=effective_limits["fetch_timeout_seconds"],
                env=env,
            )
            subprocess.run(
                base + ["-C", str(target), "checkout", "--detach", "FETCH_HEAD"],
                check=True,
                capture_output=True,
                timeout=effective_limits["checkout_timeout_seconds"],
                env=env,
            )
            resolved = subprocess.run(
                base + ["-C", str(target), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=effective_limits["checkout_timeout_seconds"],
                env=env,
            ).stdout.strip()
            if not resolved:
                raise AcquisitionError("could not resolve an immutable commit")

            size, file_count = _repo_size_bytes(target)
            if size > effective_limits["max_repo_bytes"]:
                raise AcquisitionError(
                    f"repository size {size} exceeds limit {effective_limits['max_repo_bytes']}"
                )
            if file_count > effective_limits["max_file_count"]:
                raise AcquisitionError(
                    f"repository file count {file_count} exceeds limit {effective_limits['max_file_count']}"
                )

            yield AcquisitionResult(
                path=target,
                repo_url=repo_url,
                requested_revision=revision,
                resolved_commit=resolved,
                duration_seconds=time.monotonic() - started,
                limits=effective_limits,
            )
        except subprocess.TimeoutExpired as error:
            raise AcquisitionError("repository acquisition timed out") from error
        except subprocess.CalledProcessError as error:
            raise AcquisitionError("repository could not be fetched or checked out") from error


def receipt_header(result: AcquisitionResult) -> dict:
    return {
        "schema": "pubskill-lib.receipt",
        "version": 1,
        "repository": {
            "url": result.repo_url,
            "requested_revision": result.requested_revision,
            "resolved_commit": result.resolved_commit,
        },
        "acquisition": {
            "allowlist_hosts": sorted(ALLOWED_GIT_HOSTS),
            "limits": result.limits,
            "duration_seconds": round(result.duration_seconds, 3),
            "executes_target_code": False,
            "installs_target_dependencies": False,
            "runs_target_tests": False,
        },
    }
