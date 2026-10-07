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
    return skill_dir


def _resource_map(skill_dir: Path) -> dict[str, Path]:
    """Trusted mapping of relative resource paths to filesystem paths."""
    resources: dict[str, Path] = {}
    for path in skill_dir.rglob("*"):
        if not path.is_file() or path.name == "SKILL.md" or path.is_symlink():
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
    """Return one non-SKILL.md resource inside a skill directory."""
    entry = _skill_entry(name)
    if entry is None:
        raise KeyError(name)
    if (
        not isinstance(relative, str)
        or not relative
        or "\x00" in relative
        or "\\" in relative
        or relative.startswith("/")
        or not _RESOURCE_PATH_RE.fullmatch(relative)
    ):
        raise ValueError("invalid resource path")
    if any(part in ("", ".", "..") for part in relative.split("/")):
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
