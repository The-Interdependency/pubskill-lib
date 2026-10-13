"""Transport-neutral application functions for the versioned pubskill API.

HTTP and MCP adapters must call these functions; neither adapter may maintain a
second catalog, reimplement collection, or scrape the website.
"""
from __future__ import annotations

from . import catalog as catalog_module
from . import collections as collections_module
from . import metapat_adapter
from . import queries as queries_module
from .acquisition import acquire_repository, receipt_header
from .identity import response_envelope


MAX_REQUIREMENTS = 20
MAX_REQUIREMENT_LENGTH = 256


def reject_unknown_fields(data: object, allowed: set[str], name: str) -> dict:
    """Reject request objects that carry fields outside the declared surface."""
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"unknown fields in {name}: {', '.join(unknown)}")
    return data


def validate_requirement_arrays(value: object, name: str) -> tuple[str, ...]:
    """Cap, deduplicate and validate collection requirement arrays."""
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{name} must be an array of non-empty strings")
    if len(value) > MAX_REQUIREMENTS:
        raise ValueError(f"{name} supports at most {MAX_REQUIREMENTS} entries")
    if any(len(item) > MAX_REQUIREMENT_LENGTH for item in value):
        raise ValueError(f"{name} entries must be at most {MAX_REQUIREMENT_LENGTH} characters")
    return tuple(dict.fromkeys(value))


def validate_limit(value: object, default: int, maximum: int) -> int:
    """Validate an integer limit, rejecting booleans and out-of-range values."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"limit must be an integer between 1 and {maximum}")
    return value


def _is_valid_collection(collection: object) -> bool:
    """Structural validation for caller-supplied schema-2 collections."""
    if not isinstance(collection, dict):
        return False
    if collection.get("schema") != "the-interdependency.msdmd-collection":
        return False
    if collection.get("schema_version") != "2.0.0":
        return False
    if not isinstance(collection.get("repo"), str) or not collection["repo"]:
        return False
    if not isinstance(collection.get("source"), dict):
        return False
    source = collection["source"]
    for key in ("revision_kind", "revision", "repository"):
        if not isinstance(source.get(key), str) or not source[key]:
            return False
    if not isinstance(collection.get("coverage"), dict):
        return False
    if not isinstance(collection["coverage"].get("denominator"), dict):
        return False
    for key in ("facts", "declarations", "edges", "diagnostics", "reader_manifests", "reader_runs"):
        value = collection.get(key)
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            return False
    return True


def validate_optional_str(value: object, name: str) -> str | None:
    """Reject non-string optional filter values with a client error."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def v1_identity() -> dict:
    return response_envelope(
        "identity",
        {
            "runtime_status": collections_module.runtime_status(),
        },
    )


def v1_list_skills() -> dict:
    skills = catalog_module.list_skills()
    return response_envelope(
        "skills.list",
        {"skill_count": len(skills), "skills": skills},
    )


def v1_get_skill(name: str) -> dict:
    try:
        skill = catalog_module.get_skill(name)
    except KeyError:
        raise ValueError(f"unknown skill: {name}") from None
    except RuntimeError as error:
        raise ValueError(str(error)) from None
    return response_envelope("skills.get", {"skill": skill}, input_identity={"skill": name})


def v1_get_resource(name: str, relative: str) -> dict:
    try:
        resource = catalog_module.get_resource(name, relative)
    except KeyError:
        raise ValueError(f"unknown resource: {name}/{relative}") from None
    except RuntimeError as error:
        raise ValueError(str(error)) from None
    return response_envelope(
        "skills.resource",
        {"resource": resource},
        input_identity={"skill": name, "path": relative},
    )


def v1_resolve(query: str, limit: int | None = None) -> dict:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if len(query) > 1024:
        raise ValueError("query must be at most 1024 characters")
    if len(catalog_module._tokens(query)) > 64:
        raise ValueError("query must contain at most 64 searchable tokens")
    kwargs = {"limit": validate_limit(limit, 10, 50)}
    resolved = catalog_module.resolve_skills(query, **kwargs)
    return response_envelope("skills.resolve", resolved, input_identity={"query": query})


def v1_collect(
    repo_url: str,
    revision: str | None = None,
    require_sources: tuple[str, ...] = (),
    require_facts: tuple[str, ...] = (),
) -> dict:
    """Acquire one allowed repository and collect schema-2 MSDMD metadata.

    Acquisition limits are always the server defaults; callers cannot override
    them. The repository worktree exists only while the receipt and collection
    are built; it is deleted before this function returns.
    """
    input_identity = {"repo_url": repo_url, "revision": revision}
    with acquire_repository(repo_url, revision=revision) as acquired:
        receipt = receipt_header(acquired)
        collection_result = collections_module.collect_metadata(
            acquired.path,
            repo_url,
            revision=acquired.resolved_commit,
            strict=True,
            max_file_bytes=acquired.limits["max_per_file_bytes"],
            require_sources=require_sources,
            require_facts=require_facts,
            max_output_chars=acquired.limits["max_collection_output_chars"],
        )
        receipt["collection"] = {
            "schema": collection_result.collection.get("schema"),
            "schema_version": collection_result.collection.get("schema_version"),
            "returncode": collection_result.returncode,
        }
        return response_envelope(
            "msdmd.collect",
            {
                "receipt": receipt,
                "collection": collection_result.collection,
                "runtime_status": collections_module.runtime_status(),
            },
            input_identity=input_identity,
        )


def v1_query(
    collection: dict | None = None,
    *,
    repo_url: str | None = None,
    revision: str | None = None,
    convention: str | None = None,
    fact_kind: str | None = None,
    standing: str | None = None,
    subject_contains: str | None = None,
    path_glob: str | None = None,
    diagnostic_status: str | None = None,
    diagnostics_only: bool = False,
    limit: int = 200,
) -> dict:
    """Read-only query over a supplied or freshly collected schema-2 collection."""
    input_identity: dict[str, object] = {}
    if collection is None:
        if not repo_url:
            raise ValueError("collection or repo_url is required")
        input_identity = {"repo_url": repo_url, "revision": revision}
        collected = v1_collect(repo_url, revision)
        collection = collected["collection"]
    else:
        if not _is_valid_collection(collection):
            raise ValueError("collection is not a valid schema-2 MSDMD collection")
        input_identity = {"collection_schema": collection.get("schema")}

    result = queries_module.query_collection(
        collection,
        convention=convention,
        fact_kind=fact_kind,
        standing=standing,
        subject_contains=subject_contains,
        path_glob=path_glob,
        diagnostic_status=diagnostic_status,
        diagnostics_only=diagnostics_only,
        limit=limit,
    )
    return response_envelope("msdmd.query", result, input_identity=input_identity)


def v1_metapat_catalog() -> dict:
    """Expose the current METAPAT catalog identity (adapter must be enabled)."""
    identity = metapat_adapter.metapat_catalog_identity()
    return response_envelope("metapat.catalog", identity)


def v1_metapat_recurrence(evidence: dict) -> dict:
    """Adjudicate one fully typed METAPAT recurrence evidence record."""
    decision = metapat_adapter.classify_recurrence(evidence)
    return response_envelope(
        "metapat.recurrence",
        {"decision": decision},
        input_identity={
            "source_domain": evidence.get("source_domain"),
            "target_domain": evidence.get("target_domain"),
        },
    )
