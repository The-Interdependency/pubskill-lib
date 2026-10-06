#!/usr/bin/env python3
"""Build the deterministic pubskill skill-catalog manifest.

The manifest is derived from the vendored producer `skills.json` and the
propagated skill directories under `.agents/skills/`. It is never maintained
by hand. Re-running this tool must reproduce the committed catalog byte for
byte; tests enforce that replay.

Digest scope:
  - per-skill `digest`: SHA-256 over every file in `.agents/skills/<name>/`,
    hashed as sorted relative path + NUL + file bytes + NUL.
  - `skills_json_digest`: SHA-256 of the vendored producer `skills.json` bytes.
  - `propagated_set_digest`: SHA-256 over the sorted per-skill digest pairs,
    the skills.json digest, and the shared doctrine tree digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"
SOURCE_JSON = ROOT / "src" / "pubskill_lib" / "_source.json"
DEFAULT_OUT = SKILLS_ROOT / "catalog.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_tree(path: Path) -> str:
    """SHA-256 over sorted (relative path, bytes) pairs in a directory.

    Generated interpreter/cache artifacts (`__pycache__`, `*.pyc`) are excluded
    so replay is stable across local test runs and clean checkouts.
    """
    if not path.is_dir():
        raise ValueError(f"not a directory: {path}")
    hasher = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if not file.is_file():
            continue
        if any(part == "__pycache__" for part in file.parts):
            continue
        if file.suffix == ".pyc":
            continue
        relative = file.relative_to(path).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(file.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def load_source_pin(source_json: Path) -> tuple[str, str]:
    source = json.loads(source_json.read_text(encoding="utf-8"))
    repository = source.get("repository")
    commit = source.get("commit")
    if not isinstance(repository, str) or not isinstance(commit, str):
        raise ValueError(f"invalid source pin document: {source_json}")
    return repository, commit


def build_manifest(skills_root: Path = SKILLS_ROOT, source_json: Path = SOURCE_JSON) -> dict:
    repository, commit = load_source_pin(source_json)
    index_path = skills_root / "skills.json"
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes.decode("utf-8"))
    raw_skills = index.get("skills")
    if not isinstance(raw_skills, list):
        raise ValueError(f"{index_path} has no skills array")

    names: set[str] = set()
    skills: list[dict] = []
    for entry in raw_skills:
        if not isinstance(entry, dict):
            raise ValueError(f"non-object skill entry in {index_path}")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"skill entry missing name in {index_path}")
        if name in names:
            raise ValueError(f"duplicate skill name in {index_path}: {name}")
        names.add(name)
        skill_dir = skills_root / name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise ValueError(f"vendored skill missing SKILL.md: {skill_dir}")
        declared_path = entry.get("path")
        if not isinstance(declared_path, str) or declared_path != f"{name}/SKILL.md":
            raise ValueError(f"skill {name} has unexpected path {declared_path!r}")
        skills.append(
            {
                "name": name,
                "description": entry.get("description"),
                "kind": entry.get("kind"),
                "status": entry.get("status"),
                "path": declared_path,
                "source_commit": commit,
                "digest": digest_tree(skill_dir),
            }
        )

    installed = {
        path.parent.name
        for path in skills_root.glob("*/SKILL.md")
        if path.parent.name != "doctrine"
    }
    unexpected = sorted(installed - names)
    if unexpected:
        raise ValueError(
            "vendored skill directories not present in producer index: "
            + ", ".join(unexpected)
        )

    skills_json_digest = sha256_bytes(index_bytes)
    doctrine_digest = digest_tree(skills_root / "doctrine")
    set_hasher = hashlib.sha256()
    for skill in skills:
        set_hasher.update(skill["name"].encode("utf-8"))
        set_hasher.update(b"\0")
        set_hasher.update(skill["digest"].encode("ascii"))
        set_hasher.update(b"\0")
    set_hasher.update(skills_json_digest.encode("ascii"))
    set_hasher.update(b"\0")
    set_hasher.update(doctrine_digest.encode("ascii"))
    set_hasher.update(b"\0")

    return {
        "schema": "pubskill-lib.catalog",
        "version": 1,
        "producer": {"repository": repository, "commit": commit},
        "skill_count": len(skills),
        "skills_json_digest": skills_json_digest,
        "doctrine_digest": doctrine_digest,
        "propagated_set_digest": set_hasher.hexdigest(),
        "skills": skills,
    }


def render(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output path (default: .agents/skills/catalog.json)")
    parser.add_argument("--skills-root", type=Path, default=SKILLS_ROOT, help="Skills install root (default: .agents/skills)")
    parser.add_argument("--source-json", type=Path, default=SOURCE_JSON, help="Source pin document (default: src/pubskill_lib/_source.json)")
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(skills_root=args.skills_root, source_json=args.source_json)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"catalog build failed: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(render(manifest))
    print(f"catalog: {manifest['skill_count']} skills -> {args.out}")
    print(f"producer: {manifest['producer']['repository']}@{manifest['producer']['commit']}")
    print(f"propagated_set_digest: {manifest['propagated_set_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
