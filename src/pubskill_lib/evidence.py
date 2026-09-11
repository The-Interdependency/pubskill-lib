"""Evidence engine: inventory actual code before describing it.

Language comment markers are loaded from the vendored canonical msdmd parser;
this module does not maintain a second registry.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import boundary

SHEBANG_RE = re.compile(r"^#!.*$")
_RATIOS_LINE_RE = re.compile(r"^(?:#|//|--|%|;|!|'|\*>)\s*ratios:\s*(.+?)\s*$")


@lru_cache(maxsize=1)
def _comment_markers() -> dict[str, str]:
    """Load COMMENT_MARKERS from the pinned repo-local msdmd parser."""
    repo = Path(__file__).resolve().parents[2]
    parser_path = repo / ".agents" / "skills" / "msdmd" / "parsers" / "universal.py"
    spec = importlib.util.spec_from_file_location("pubskill_lib._vendored_msdmd", parser_path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    markers = getattr(module, "COMMENT_MARKERS", {})
    return dict(markers) if isinstance(markers, dict) else {}


@dataclass
class FileEvidence:
    path: str
    language: str
    marker: str | None
    shebang: str | None = None
    ratios_lines: list[str] = field(default_factory=list)
    msdmd_blocks: dict[str, list[dict]] = field(default_factory=dict)
    narrative_entries: list[dict] = field(default_factory=list)
    sha256: str = ""
    size: int = 0
    executable: bool = False
    hmmm: list[str] = field(default_factory=list)


def _block_name_re(marker: str) -> re.Pattern[str]:
    m = re.escape(marker)
    return re.compile(
        rf"^{m} === ([A-Z_]+) ===\s*$(?P<body>.*?)^{m} === END \1 ===\s*$",
        re.MULTILINE | re.DOTALL,
    )


def _parse_block_entries(marker: str, body: str) -> list[dict]:
    m = re.escape(marker)
    id_re = re.compile(rf"^\s*{m}\s*id:\s*(?P<id>\S+)\s*$")
    field_re = re.compile(rf"^\s*{m}\s+(?P<key>[a-z_]+):\s*(?P<val>.+?)\s*$")
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in body.splitlines():
        line = line.rstrip()
        match_id = id_re.match(line)
        if match_id:
            if current is not None:
                entries.append(current)
            current = {"id": match_id.group("id")}
            continue
        if current is None:
            continue
        match_field = field_re.match(line)
        if match_field:
            current[match_field.group("key")] = match_field.group("val")
    if current is not None:
        entries.append(current)
    return entries


def read_evidence(root: Path, path: Path) -> FileEvidence:
    root = Path(root).resolve()
    rel = str(path.relative_to(root))
    marker = _comment_markers().get(path.suffix.lower())
    language = path.suffix.lower().lstrip(".") or "unknown"
    item = FileEvidence(path=rel, language=language, marker=marker)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        item.hmmm.append("unreadable file")
        return item

    encoded = text.encode("utf-8", errors="replace")
    item.sha256 = hashlib.sha256(encoded).hexdigest()
    item.size = len(encoded)
    try:
        item.executable = bool(path.stat().st_mode & 0o111)
    except OSError:
        pass

    first_line = text.splitlines()[0].rstrip() if text.splitlines() else ""
    if SHEBANG_RE.match(first_line):
        item.shebang = first_line

    if marker is not None:
        for raw in text.splitlines():
            if _RATIOS_LINE_RE.match(raw.rstrip()):
                item.ratios_lines.append(raw.rstrip())
        for match in _block_name_re(marker).finditer(text):
            name = match.group(1)
            entries = _parse_block_entries(marker, match.group("body"))
            item.msdmd_blocks.setdefault(name, []).extend(entries)
        item.narrative_entries = item.msdmd_blocks.get("NARRATIVE", [])
    else:
        item.hmmm.append(f"unsupported language for msdmd: .{language}")
    return item


def inventory(root: Path) -> list[FileEvidence]:
    root = boundary.assert_inside(root, root)
    return [read_evidence(root, path) for path in boundary.iter_files(root)]
