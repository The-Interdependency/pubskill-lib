"""Optional, bounded METAPAT recurrence adapter.

METAPAT is an exact-pin, digest-checked consumer. This module never copies
METAPAT canon into pubskill and never edits it. It exposes the current METAPAT
catalog identity and `adjudicate_recurrence` over fully typed evidence, and it
fails closed whenever the installed METAPAT source is not the pinned commit.

The three transfer flags are always ``False``; this adapter re-asserts that
after adjudication and refuses to serialize any other value.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .identity import REPO_ROOT

METAPAT_REPOSITORY = "The-Interdependency/metapat"
METAPAT_COMMIT = "86415a5368c1a1417c2b6731f19967a6b1fce6bb"
METAPAT_PACKAGE = "src/metapat"

REQUIRED_MODULE_IDS = (
    "metapat.axiom.12.domain_qualification",
    "metapat.postulate.1.partial_domains",
    "metapat.postulate.6.cross_domain_falsification",
    "metapat.theory.11.cross_domain_reconstruction",
)

_EVIDENCE_REQUIRED = {
    "source_domain",
    "target_domain",
    "source_origin_id",
    "target_origin_id",
    "source_path_id",
    "target_path_id",
    "declared_invariants",
    "preserved_invariants",
    "mapping_complete",
    "replay_passed",
    "catalog_version",
    "catalog_digest",
    "catalog_module_ids",
}
_EVIDENCE_OPTIONAL = {
    "equivalence_proof_id",
    "shared_ancestry",
    "ancestry_resolved",
    "unresolved",
}


class MetapatUnavailable(RuntimeError):
    """METAPAT is not enabled, not pinned, or failed its identity check."""


def candidate_roots() -> list[Path]:
    roots = []
    override = os.environ.get("PUBSKILL_METAPAT_ROOT")
    if override:
        roots.append(Path(override).expanduser().resolve())
    sibling = REPO_ROOT.parent / "metapat"
    if sibling.is_dir():
        roots.append(sibling.resolve())
    return roots


def _head_of(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _is_clean(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.returncode == 0 and not result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False


def verified_metapat_root() -> Path | None:
    """Return a METAPAT checkout only when its HEAD is the exact pinned commit
    and the worktree is clean; dirty checkouts fail closed as unverified."""
    for root in candidate_roots():
        if not (root / METAPAT_PACKAGE).is_dir():
            continue
        if _head_of(root) == METAPAT_COMMIT and _is_clean(root):
            return root
    return None


def is_metapat_enabled() -> bool:
    return verified_metapat_root() is not None


def _import_metapat():
    root = verified_metapat_root()
    if root is None:
        raise MetapatUnavailable(
            "METAPAT adapter is not enabled; set PUBSKILL_METAPAT_ROOT to a "
            f"checkout of {METAPAT_REPOSITORY} at {METAPAT_COMMIT}"
        )
    package_src = str(root / "src")
    if package_src not in sys.path:
        sys.path.insert(0, package_src)
    from metapat.catalog import CATALOG_VERSION, canonical_semantic_catalog
    from metapat.structural_recurrence import RecurrenceEvidence, adjudicate_recurrence

    return CATALOG_VERSION, canonical_semantic_catalog, RecurrenceEvidence, adjudicate_recurrence


def metapat_catalog_identity() -> dict:
    """Expose the current catalog identity required to build valid evidence."""
    catalog_version, canonical_catalog, _, _ = _import_metapat()
    return {
        "enabled": True,
        "repository": METAPAT_REPOSITORY,
        "commit": METAPAT_COMMIT,
        "catalog_version": catalog_version,
        "catalog_digest": canonical_catalog().catalog_digest,
        "required_module_ids": list(REQUIRED_MODULE_IDS),
        "module_ids": [module.module_id for module in canonical_catalog().modules],
    }


def _validate_evidence_fields(evidence: dict) -> dict:
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a JSON object")
    unknown = sorted(set(evidence) - (_EVIDENCE_REQUIRED | _EVIDENCE_OPTIONAL))
    if unknown:
        raise ValueError(f"unknown fields in recurrence evidence: {', '.join(unknown)}")
    missing = sorted(_EVIDENCE_REQUIRED - set(evidence))
    if missing:
        raise ValueError(f"missing fields in recurrence evidence: {', '.join(missing)}")
    return evidence


def classify_recurrence(evidence: dict) -> dict:
    """Adjudicate one fully typed recurrence evidence record.

    Returns the complete decision with all three transfer flags false. The
    adapter never supplies missing evidence and never verifies an equivalence
    proof; METAPAT owns the outcome.
    """
    evidence = _validate_evidence_fields(evidence)
    catalog_version, canonical_catalog, RecurrenceEvidence, adjudicate_recurrence = _import_metapat()

    current_digest = canonical_catalog().catalog_digest
    if evidence.get("catalog_version") != catalog_version:
        raise MetapatUnavailable(
            f"catalog version mismatch: evidence {evidence.get('catalog_version')!r}, current {catalog_version!r}"
        )
    if evidence.get("catalog_digest") != current_digest:
        raise MetapatUnavailable("catalog digest mismatch: evidence does not bind the current METAPAT catalog")

    normalized = dict(evidence)
    for name in ("declared_invariants", "preserved_invariants", "catalog_module_ids", "shared_ancestry", "unresolved"):
        if name in normalized and normalized[name] is not None:
            normalized[name] = tuple(normalized[name])
    normalized.setdefault("equivalence_proof_id", None)
    normalized.setdefault("shared_ancestry", ())
    normalized.setdefault("ancestry_resolved", False)
    normalized.setdefault("unresolved", ())

    try:
        record = RecurrenceEvidence(**normalized)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid recurrence evidence: {error}") from error

    decision = adjudicate_recurrence(record)
    for flag in ("semantic_transfer", "proof_status_transfer", "measurement_status_transfer"):
        if getattr(decision, flag) is not False:
            raise MetapatUnavailable(f"METAPAT returned {flag}={getattr(decision, flag)!r}; refusing to serialize")

    return {
        "outcome": decision.outcome,
        "independent": decision.independent,
        "source_domain": decision.source_domain,
        "target_domain": decision.target_domain,
        "source_origin_id": decision.source_origin_id,
        "target_origin_id": decision.target_origin_id,
        "source_path_id": decision.source_path_id,
        "target_path_id": decision.target_path_id,
        "catalog_version": decision.catalog_version,
        "catalog_digest": decision.catalog_digest,
        "catalog_module_ids": list(decision.catalog_module_ids),
        "declared_invariants": list(decision.declared_invariants),
        "preserved_invariants": list(decision.preserved_invariants),
        "shared_ancestry": list(decision.shared_ancestry),
        "equivalence_proof_id": decision.equivalence_proof_id,
        "mapping_complete": decision.mapping_complete,
        "replay_passed": decision.replay_passed,
        "ancestry_resolved": decision.ancestry_resolved,
        "unresolved": list(decision.unresolved),
        "semantic_transfer": decision.semantic_transfer,
        "proof_status_transfer": decision.proof_status_transfer,
        "measurement_status_transfer": decision.measurement_status_transfer,
    }
