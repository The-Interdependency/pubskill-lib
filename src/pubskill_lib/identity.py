"""Pubskill identity resolution.

Canonical producer and consumer identities come from checked-in source pin
documents, never from request parameters. The vendored skills root is resolved
from the repository checkout first, then a packaged copy, then an explicit
environment override.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
SOURCE_JSON = PACKAGE_ROOT / "_source.json"


def skills_root() -> Path:
    """Return the vendored skills install root.

    Resolution order: PUBSKILL_SKILLS_ROOT, repo checkout `.agents/skills`,
    packaged `pubskill_lib/_skills`.
    """
    override = os.environ.get("PUBSKILL_SKILLS_ROOT")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_dir():
            raise RuntimeError(f"PUBSKILL_SKILLS_ROOT is not a directory: {path}")
        return path
    checkout = REPO_ROOT / ".agents" / "skills"
    if checkout.is_dir():
        return checkout
    packaged = PACKAGE_ROOT / "_skills"
    if packaged.is_dir():
        return packaged
    raise RuntimeError(
        "vendored skills root not found; set PUBSKILL_SKILLS_ROOT to .agents/skills"
    )


def producer_identity() -> dict[str, str]:
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    if source.get("schema") != "pubskill-lib.source" or source.get("version") != 1:
        raise RuntimeError(f"invalid source pin document: {SOURCE_JSON}")
    repository = source.get("repository")
    commit = source.get("commit")
    if not isinstance(repository, str) or not isinstance(commit, str):
        raise RuntimeError(f"invalid source pin document: {SOURCE_JSON}")
    return {"repository": repository, "commit": commit}


def consumer_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else "hmmm"
    except OSError:
        return "hmmm"


def consumer_identity() -> dict[str, str]:
    return {"repository": "The-Interdependency/pubskill-lib", "commit": consumer_commit()}


def catalog_identity() -> dict[str, str]:
    catalog = json.loads((skills_root() / "catalog.json").read_text(encoding="utf-8"))
    if catalog.get("schema") != "pubskill-lib.catalog":
        raise RuntimeError("invalid catalog manifest")
    producer = catalog.get("producer", {})
    return {
        "catalog_schema": catalog["schema"],
        "catalog_version": catalog["version"],
        "catalog_digest": catalog.get("propagated_set_digest", "hmmm"),
        "producer_repository": producer.get("repository", "hmmm"),
        "producer_commit": producer.get("commit", "hmmm"),
    }


def build_identity() -> dict[str, object]:
    """Stable identity block for every v1 response."""
    return {
        "schema": "pubskill-lib.api",
        "version": 1,
        "producer": producer_identity(),
        "consumer": consumer_identity(),
        "catalog": catalog_identity(),
    }


def response_envelope(route: str, payload: dict[str, object], input_identity: dict[str, object] | None = None) -> dict[str, object]:
    envelope: dict[str, object] = {
        "schema": "pubskill-lib.api",
        "version": 1,
        "identity": build_identity(),
        "route": route,
    }
    if input_identity:
        envelope["input_identity"] = input_identity
    envelope.update(payload)
    return envelope
