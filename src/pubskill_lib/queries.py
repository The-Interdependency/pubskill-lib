"""Read-only filtering over a validated schema-2 MSDMD collection."""
from __future__ import annotations

import fnmatch
from typing import Any, Callable

_FACT_KEYS = ("address", "convention", "extraction", "kind", "native", "origin", "source", "standing", "subject")
_DIAGNOSTIC_KEYS = ("code", "status", "severity", "message", "reader_id", "source", "subject")


def _matches(item: dict, needle: str, key: str) -> bool:
    value = item.get(key)
    return isinstance(value, str) and needle.lower() in value.lower()


def _convention_matches(item: dict, convention: str) -> bool:
    value = item.get("convention")
    if isinstance(value, str):
        return value == convention
    if isinstance(value, dict):
        return convention in value.values()
    return False


def query_collection(
    collection: dict,
    *,
    convention: str | None = None,
    fact_kind: str | None = None,
    standing: str | None = None,
    subject_contains: str | None = None,
    path_glob: str | None = None,
    diagnostic_status: str | None = None,
    diagnostics_only: bool = False,
    limit: int = 200,
) -> dict:
    """Filter a collection's facts, declarations, edges and diagnostics.

    All predicates are read-only string/glob matches over already-collected
    records; nothing is re-extracted or inferred here.
    """
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")

    facts = collection.get("facts", [])
    declarations = collection.get("declarations", [])
    edges = collection.get("edges", [])
    diagnostics = collection.get("diagnostics", [])

    def fact_ok(item: dict) -> bool:
        if convention and not _convention_matches(item, convention):
            return False
        if fact_kind and item.get("kind") != fact_kind:
            return False
        if standing and item.get("standing") != standing:
            return False
        if subject_contains and not _matches(item, subject_contains, "subject"):
            return False
        if path_glob:
            source = item.get("source", {})
            path = source.get("path") if isinstance(source, dict) else None
            if not isinstance(path, str) or not fnmatch.fnmatchcase(path, path_glob):
                return False
        return True

    def decl_ok(item: dict) -> bool:
        if convention and not _convention_matches(item, convention):
            return False
        if fact_kind and item.get("kind") != fact_kind:
            return False
        if subject_contains and not _matches(item, subject_contains, "subject"):
            return False
        return True

    def edge_ok(item: dict) -> bool:
        if convention and not _convention_matches(item, convention):
            return False
        if fact_kind and item.get("kind") != fact_kind:
            return False
        return True

    def diag_ok(item: dict) -> bool:
        if diagnostic_status and item.get("status") != diagnostic_status:
            return False
        if convention and not _convention_matches(item, convention):
            return False
        return True

    matched_facts = [item for item in facts if fact_ok(item)][:limit]
    matched_declarations = [] if diagnostics_only else [item for item in declarations if decl_ok(item)][:limit]
    matched_edges = [] if diagnostics_only else [item for item in edges if edge_ok(item)][:limit]
    matched_diagnostics = [item for item in diagnostics if diag_ok(item)][:limit]

    return {
        "collection_schema": collection.get("schema"),
        "collection_schema_version": collection.get("schema_version"),
        "repo": collection.get("repo"),
        "source": collection.get("source"),
        "filters": {
            "convention": convention,
            "fact_kind": fact_kind,
            "standing": standing,
            "subject_contains": subject_contains,
            "path_glob": path_glob,
            "diagnostic_status": diagnostic_status,
            "diagnostics_only": diagnostics_only,
            "limit": limit,
        },
        "counts": {
            "matched_facts": len(matched_facts),
            "matched_declarations": len(matched_declarations),
            "matched_edges": len(matched_edges),
            "matched_diagnostics": len(matched_diagnostics),
            "total_facts": len(facts),
            "total_declarations": len(declarations),
            "total_edges": len(edges),
            "total_diagnostics": len(diagnostics),
        },
        "matched_facts": matched_facts,
        "matched_declarations": matched_declarations,
        "matched_edges": matched_edges,
        "matched_diagnostics": matched_diagnostics,
        "coverage": collection.get("coverage"),
        "reader_manifests": collection.get("reader_manifests"),
        "reader_runs": collection.get("reader_runs"),
    }


def query_facts(collection: dict, predicate: Callable[[dict], bool] | None = None) -> list[dict]:
    facts = collection.get("facts", [])
    return [fact for fact in facts if predicate is None or predicate(fact)]
