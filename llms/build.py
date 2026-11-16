# ratios: loc_comments=229:5 imports_exports=6:7 calls_definitions=66:12
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


_MARKERS: dict[str, str] = {
    ".md": "#",
    ".markdown": "#",
    ".py": "#",
    ".rb": "#",
    ".ex": "#",
    ".exs": "#",
    ".sh": "#",
    ".ts": "//",
    ".tsx": "//",
    ".js": "//",
    ".jsx": "//",
    ".mjs": "//",
    ".rs": "//",
    ".go": "//",
    ".java": "//",
    ".c": "//",
    ".cpp": "//",
    ".cc": "//",
    ".h": "//",
    ".hpp": "//",
    ".swift": "//",
    ".kt": "//",
    ".sql": "--",
    ".lua": "--",
    ".hs": "--",
}

_DEFAULT_SKIP = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "tests",
}


@dataclass
class Entry:
    file: Path
    id: str
    fields: dict[str, str]


def marker_for(path: Path) -> str | None:
    return _MARKERS.get(path.suffix.lower())


def _markdown_without_fenced_code(text: str) -> str:
    """Replace fenced-code bodies with blank lines so examples are not parsed."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def parse_text(text: str, marker: str = "#", *, source: Path | None = None) -> list[Entry]:
    """Parse LLMS entries from one file.

    This is intentionally small and stdlib-only. It follows msdmd shape while
    allowing key-definition field names such as ``char-compress``.
    """
    if source is not None and source.suffix.lower() in {".md", ".markdown"}:
        text = _markdown_without_fenced_code(text)

    entries: list[Entry] = []
    in_block = False
    current_id: str | None = None
    current_fields: dict[str, str] = {}
    current_field: str | None = None
    source_path = source or Path("<memory>")

    def emit() -> None:
        nonlocal current_id, current_fields, current_field
        if current_id is not None:
            entries.append(Entry(source_path, current_id, dict(current_fields)))
        current_id = None
        current_fields = {}
        current_field = None

    prefix = f"{marker} "
    open_line = f"{marker} === LLMS ==="
    close_line = f"{marker} === END LLMS ==="

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped == open_line:
            in_block = True
            emit()
            continue
        if stripped == close_line and in_block:
            emit()
            in_block = False
            continue
        if not in_block:
            continue

        if not stripped.startswith(prefix):
            continue
        body = stripped[len(prefix):]

        if body.startswith("id:"):
            emit()
            current_id = body.split(":", 1)[1].strip()
            continue

        if current_id is None:
            continue

        if body == "":
            if current_field:
                current_fields[current_field] = current_fields[current_field] + "\n"
            continue

        if body.startswith("  ") and ":" in body:
            key, value = body.strip().split(":", 1)
            current_field = key.strip()
            current_fields[current_field] = value.strip()
            continue

        if body.startswith("    ") and current_field:
            continuation = body[4:]
            current_fields[current_field] = current_fields[current_field] + "\n" + continuation
            continue

    if in_block:
        emit()
    return entries


def iter_files(root: Path, skip: Iterable[str] | None = None) -> Iterable[Path]:
    skip_set = set(skip) if skip is not None else set(_DEFAULT_SKIP)

    def walk(path: Path) -> Iterable[Path]:
        if path.name in skip_set:
            return
        try:
            children = sorted(path.iterdir())
        except OSError:
            return
        for child in children:
            if child.is_dir():
                if child.name in skip_set:
                    continue
                yield from walk(child)
            elif child.is_file() and marker_for(child) is not None:
                yield child

    yield from walk(root)


def collect(root: Path) -> list[Entry]:
    entries: list[Entry] = []
    for path in iter_files(root):
        marker = marker_for(path)
        if marker is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        entries.extend(parse_text(text, marker, source=path.relative_to(root)))
    return entries


def _content_for(entries: list[Entry], entry_id: str) -> str:
    parts = [
        entry.fields.get("content", "").strip()
        for entry in entries
        if entry.id == entry_id and entry.fields.get("content", "").strip()
    ]
    return "\n\n".join(parts) if parts else "hmmm"


def _definition_lines(entries: list[Entry]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        if entry.id != "key_definitions":
            continue
        for key, value in entry.fields.items():
            if key == "content":
                continue
            lines.append(f"- **{key}** = {value.strip() or 'hmmm'}")
    return lines or ["- **hmmm** = hmmm"]


def generate(entries: list[Entry], repo_name: str) -> str:
    overview = _content_for(entries, "project_overview")
    definitions = "\n".join(_definition_lines(entries))
    architecture = _content_for(entries, "architecture_summary")
    usage = _content_for(entries, "usage_rules")

    return "\n".join(
        [
            f"# LLM Instructions for {repo_name}",
            "",
            "## Project Overview",
            overview,
            "",
            "## Key Definitions (never infer or expand these)",
            definitions,
            "",
            "## Architecture Summary",
            architecture,
            "",
            "## How to Use This Repo with LLMs / Agents",
            usage,
            "",
            "This file is a generated projection of source LLMS blocks. Owning source declarations remain authoritative. The shipped publisher is block-only; omission here does not establish absence of native information. Unsupported native instruction sources remain hmmm.",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a canonical root llms.txt from LLMS blocks.")
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--out", default="llms.txt", help="Output path, relative to --root unless absolute.")
    parser.add_argument("--apply", action="store_true", help="Write the generated file.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if the committed output differs.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path

    generated = generate(collect(root), repo_name=root.name)

    if args.apply:
        out_path.write_text(generated, encoding="utf-8")
        print(f"wrote {out_path}")

    if args.check:
        try:
            current = out_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"llms-build drift: missing {out_path}", file=sys.stderr)
            return 1
        if current != generated:
            print(f"llms-build drift: {out_path} differs from generated output", file=sys.stderr)
            return 1
        print("llms-build drift: pass")
        return 0

    if not args.apply:
        print(generated, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# ratios: loc_comments=229:5 imports_exports=6:7 calls_definitions=66:12
