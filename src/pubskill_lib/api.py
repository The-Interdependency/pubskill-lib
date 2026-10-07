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


def reject_unknown_fields(data: object, allowed: set[str], name: str) -> dict:
    """Reject request objects that carry fields outside the declared surface."""
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"unknown fields in {name}: {', '.join(unknown)}")
    return data


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
    return response_envelope("skills.get", {"skill": skill}, input_identity={"skill": name})


def v1_get_resource(name: str, relative: str) -> dict:
    try:
        resource = catalog_module.get_resource(name, relative)
    except KeyError:
        raise ValueError(f"unknown resource: {name}/{relative}") from None
    return response_envelope(
        "skills.resource",
        {"resource": resource},
        input_identity={"skill": name, "path": relative},
    )


def v1_resolve(query: str, limit: int | None = None) -> dict:
    kwargs = {"limit": 10 if limit is None else limit}
    resolved = catalog_module.resolve_skills(query, **kwargs)
    return response_envelope("skills.resolve", resolved, input_identity={"query": query})


def v1_collect(
    repo_url: str,
    revision: str | None = None,
    require_sources: tuple[str, ...] = (),
    require_facts: tuple[str, ...] = (),
    limits: dict | None = None,
) -> dict:
    """Acquire one allowed repository and collect schema-2 MSDMD metadata.

    The repository worktree exists only while the receipt and collection are
    built; it is deleted before this function returns.
    """
    input_identity = {"repo_url": repo_url, "revision": revision}
    with acquire_repository(repo_url, revision=revision, limits=limits) as acquired:
        receipt = receipt_header(acquired)
        collection_result = collections_module.collect_metadata(
            acquired.path,
            repo_url,
            revision=acquired.resolved_commit,
            strict=True,
            max_file_bytes=acquired.limits["max_per_file_bytes"],
            require_sources=require_sources,
            require_facts=require_facts,
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
        if not isinstance(collection, dict) or collection.get("schema") != "the-interdependency.msdmd-collection":
            raise ValueError("collection is not a schema-2 MSDMD collection")
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
