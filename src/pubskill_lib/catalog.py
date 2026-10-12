"""Read-only retrieval over the deterministic pubskill skill catalog.

All data comes from the checked-in catalog manifest and the vendored skill
bytes. Nothing here executes skill content or invents catalog entries.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .identity import skills_root

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "what", "when", "where", "which", "who", "with",
}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")


def load_catalog() -> dict:
    catalog = json.loads((skills_root() / "catalog.json").read_text(encoding="utf-8"))
    if catalog.get("schema") != "pubskill-lib.catalog":
        raise RuntimeError("invalid catalog manifest")
    return catalog


def _catalog_by_name(catalog: dict) -> dict[str, dict]:
    by_name = {item["name"]: item for item in catalog.get("skills", [])}
    if len(by_name) != catalog.get("skill_count"):
        raise RuntimeError("catalog has duplicate or missing skill entries")
    return by_name


def list_skills() -> list[dict]:
    """Public catalog summaries: name, description, kind, status, path, digest."""
    catalog = load_catalog()
    return [
        {
            "name": item["name"],
            "description": item.get("description"),
            "kind": item.get("kind"),
            "status": item.get("status"),
            "path": item["path"],
            "source_commit": item["source_commit"],
            "digest": item["digest"],
        }
        for item in catalog["skills"]
    ]


_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_RESOURCE_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _digest_tree(path: Path) -> str:
    """SHA-256 over sorted (relative path, bytes) pairs.

    Interpreter caches and installed reader runtimes (``__pycache__``,
    ``*.pyc``, ``node_modules``) are excluded so verification matches the
    source-pinned manifest digest in clean checkouts and deployed images.
    """
    hasher = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if not file.is_file():
            continue
        if any(part == "__pycache__" for part in file.parts):
            continue
        if any(part == "node_modules" for part in file.parts):
            continue
        if file.suffix == ".pyc":
            continue
        relative = file.relative_to(path).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(file.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _verify_skill_bytes(entry: dict, skill_dir: Path) -> None:
    """Fail closed when served bytes no longer match the pinned digest.

    The tree is revalidated on every serve so a mounted or copied skills root
    that drifts after its first request cannot keep reporting the old digest.
    """
    actual = _digest_tree(skill_dir)
    if actual != entry["digest"]:
        raise RuntimeError(
            f"skill {entry['name']} bytes do not match the pinned catalog digest"
        )


def _skill_entry(name: str) -> dict | None:
    """Return the trusted catalog entry for a validated skill name.

    The name is used only as a dictionary key; filesystem paths are derived
    from the checked-in catalog entry, never from caller input.
    """
    if not isinstance(name, str) or not _SKILL_NAME_RE.fullmatch(name):
        return None
    return _catalog_by_name(load_catalog()).get(name)


def _skill_dir_from_entry(entry: dict) -> Path:
    root = skills_root()
    skill_dir = (root / entry["path"]).resolve().parent
    if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
        raise KeyError(entry["name"])
    if skill_dir.parent != root.resolve():
        raise KeyError(entry["name"])
    _verify_skill_bytes(entry, skill_dir)
    return skill_dir


def _resource_map(skill_dir: Path) -> dict[str, Path]:
    """Trusted mapping of relative resource paths to filesystem paths.

    Generated interpreter caches are excluded so the served resource set stays
    source-pinned and deterministic, matching the catalog builder's digest
    scope.
    """
    resources: dict[str, Path] = {}
    for path in skill_dir.rglob("*"):
        if not path.is_file() or path.name == "SKILL.md" or path.is_symlink():
            continue
        if any(part == "__pycache__" for part in path.parts):
            continue
        if any(part == "node_modules" for part in path.parts):
            continue
        if path.suffix == ".pyc":
            continue
        resources[path.relative_to(skill_dir).as_posix()] = path
    return resources


def get_skill(name: str) -> dict:
    """Return one skill with its SKILL.md text and listed resources."""
    entry = _skill_entry(name)
    if entry is None:
        raise KeyError(name)
    skill_dir = _skill_dir_from_entry(entry)
    skill_md = skill_dir / "SKILL.md"
    resources = []
    for relative, path in sorted(_resource_map(skill_dir).items()):
        resources.append(
            {
                "path": relative,
                "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "name": name,
        "description": entry.get("description"),
        "kind": entry.get("kind"),
        "status": entry.get("status"),
        "source_commit": entry["source_commit"],
        "digest": entry["digest"],
        "skill_md": skill_md.read_text(encoding="utf-8"),
        "resources": resources,
    }


def get_resource(name: str, relative: str) -> dict:
    """Return one non-SKILL.md resource inside a skill directory.

    Shared ``doctrine`` documents (referenced from canonical skills via
    ``../doctrine/...``) are served under the reserved catalog name
    ``doctrine``, and source-pinned shared files at the skills root (such as
    the toolkit README referenced via ``../README.md``) are served under the
    reserved name ``shared``. ``CONNECTORS.md`` is referenced by upstream
    skills but does not exist in the pinned producer tree, so retrieval of it
    fails closed as an unknown resource.
    """
    if name == "doctrine":
        return _get_doctrine_resource(relative)
    if name == "shared":
        return _get_shared_resource(relative)
    entry = _skill_entry(name)
    if entry is None:
        raise KeyError(name)
    if not _valid_resource_path(relative):
        raise ValueError("invalid resource path")
    resources = _resource_map(_skill_dir_from_entry(entry))
    if relative not in resources:
        raise KeyError(relative)
    path = resources[relative]
    data = path.read_bytes()
    return {
        "name": name,
        "path": relative,
        "digest": hashlib.sha256(data).hexdigest(),
        "content_utf8": data.decode("utf-8", errors="strict"),
    }


def _valid_resource_path(relative: object) -> bool:
    if not isinstance(relative, str) or not relative:
        return False
    if "\x00" in relative or "\\" in relative or relative.startswith("/"):
        return False
    if not _RESOURCE_PATH_RE.fullmatch(relative):
        return False
    return not any(part in ("", ".", "..") for part in relative.split("/"))


def _doctrine_resource_map() -> dict[str, Path]:
    """Trusted mapping of shared doctrine documents to filesystem paths."""
    resources: dict[str, Path] = {}
    doctrine_root = skills_root() / "doctrine"
    if not doctrine_root.is_dir():
        return resources
    for path in doctrine_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part == "__pycache__" for part in path.parts) or path.suffix == ".pyc":
            continue
        resources[path.relative_to(doctrine_root).as_posix()] = path
    return resources


def _get_doctrine_resource(relative: str) -> dict:
    if not _valid_resource_path(relative):
        raise ValueError("invalid resource path")
    resources = _doctrine_resource_map()
    if relative not in resources:
        raise KeyError(relative)
    path = resources[relative]
    data = path.read_bytes()
    return {
        "name": "doctrine",
        "path": relative,
        "digest": hashlib.sha256(data).hexdigest(),
        "content_utf8": data.decode("utf-8", errors="strict"),
    }


def _get_shared_resource(relative: str) -> dict:
    if not _valid_resource_path(relative):
        raise ValueError("invalid resource path")
    root = skills_root()
    allowed = {"README.md"}
    if relative not in allowed:
        raise KeyError(relative)
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise KeyError(relative)
    data = path.read_bytes()
    return {
        "name": "shared",
        "path": relative,
        "digest": hashlib.sha256(data).hexdigest(),
        "content_utf8": data.decode("utf-8", errors="strict"),
    }


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def resolve_skills(query: str, limit: int = 10) -> dict:
    """Rank catalog skills by keyword overlap over name and description.

    This is a candidate ranking, not an authority decision. The score and
    method are always returned; a client decides which skill to load.
    """
    query_tokens = _tokens(query or "")
    if not query_tokens:
        raise ValueError("query must contain at least one searchable token")
    catalog = load_catalog()
    scored = []
    for item in catalog["skills"]:
        name_tokens = _tokens(item["name"])
        description_tokens = _tokens(item.get("description") or "")
        score = 0.0
        matched = []
        for token in query_tokens:
            if token in name_tokens:
                score += 1.0
                matched.append(token)
            elif token in description_tokens:
                score += 0.5
                matched.append(token)
        if score > 0:
            scored.append(
                {
                    "name": item["name"],
                    "score": score,
                    "matched_tokens": sorted(set(matched)),
                    "digest": item["digest"],
                }
            )
    scored.sort(key=lambda item: (-item["score"], item["name"]))
    return {
        "method": "keyword-overlap-v1",
        "authoritative": False,
        "query": query,
        "candidates": scored[: max(1, min(limit, 50))],
        "total_matches": len(scored),
    }
