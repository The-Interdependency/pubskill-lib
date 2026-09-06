"""Evidence engine: inventory actual code before describing it.

This layer never infers behavior from names, layout, or convention. It reads
files and records what is actually there: language marker, shebang, existing
msdmd blocks, existing RATIOS lines, content hash, size, and executable bit.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import boundary

# extension -> comment marker (same table as canon msdmd)
MARKERS: dict[str, str] = {
    ".py": "#", ".rb": "#", ".ex": "#", ".exs": "#", ".sh": "#",
    ".ts": "//", ".tsx": "//", ".js": "//", ".jsx": "//", ".mjs": "//",
    ".rs": "//", ".go": "//", ".java": "//", ".c": "//", ".cpp": "//",
    ".cc": "//", ".h": "//", ".hpp": "//", ".swift": "//", ".kt": "//",
    ".sql": "--", ".lua": "--", ".hs": "--",
}

SHEBANG_RE = re.compile(r"^#!.*$")
_RATIOS_LINE_RE = re.compile(r"^(?:#|//|--)\s*ratios:\s*(.+?)\s*$")
_NARRATIVE_FENCE_RE = re.compile(
    r"^(?:#|//|--) === NARRATIVE ===\s*$.*?^(?:#|//|--) === END NARRATIVE ===\s*$",
    re.MULTILINE | re.DOTALL,
)


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
    return re.compile(rf"^{m} === ([A-Z_]+) ===\s*$(?P<body>.*?)^{m} === END \1 ===\s*$", re.MULTILINE | re.DOTALL)


def _parse_block_entries(marker: str, body: str) -> list[dict]:
    m = re.escape(marker)
    id_re = re.compile(rf"^\s*{m}\s*id:\s*(?P<id>\S+)\s*$")
    field_re = re.compile(rf"^\s*{m}\s+(?P<key>[a-z_]+):\s*(?P<val>.+?)\s*$")
    entries: list[dict] = []
    current: dict[str, str] | None = None
    for line in body.splitlines():
        line = line.rstrip()
        mid = id_re.match(line)
        if mid:
            if current is not None:
                entries.append(current)
            current = {"id": mid.group("id")}
            continue
        if current is None:
            continue
        mf = field_re.match(line)
        if mf:
            current[mf.group("key")] = mf.group("val")
    if current is not None:
        entries.append(current)
    return entries


def read_evidence(root: Path, path: Path) -> FileEvidence:
    """Read one file into evidence. Never raises for unsupported files."""
    root = Path(root).resolve()
    rel = str(path.relative_to(root))
    marker = MARKERS.get(path.suffix.lower())
    language = path.suffix.lower().lstrip(".") or "unknown"
    evidence = FileEvidence(path=rel, language=language, marker=marker)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        evidence.hmmm.append("unreadable file")
        return evidence
    evidence.sha256 = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    evidence.size = len(text.encode("utf-8", errors="replace"))
    try:
        evidence.executable = bool(path.stat().st_mode & 0o111)
    except OSError:
        pass

    first_line = text.splitlines()[0].rstrip() if text.splitlines() else ""
    if SHEBANG_RE.match(first_line):
        evidence.shebang = first_line

    if marker is not None:
        for raw in text.splitlines():
            if _RATIOS_LINE_RE.match(raw.rstrip()):
                evidence.ratios_lines.append(raw.rstrip())
        block_re = _block_name_re(marker)
        for match in block_re.finditer(text):
            name = match.group(1)
            entries = _parse_block_entries(marker, match.group("body"))
            evidence.msdmd_blocks.setdefault(name, []).extend(entries)
        evidence.narrative_entries = evidence.msdmd_blocks.get("NARRATIVE", [])
    else:
        evidence.hmmm.append(f"unsupported language for msdmd: .{language}")
    return evidence


def inventory(root: Path) -> list[FileEvidence]:
    """Inventory every regular file inside the boundary."""
    root = boundary.assert_inside(root, root)
    out: list[FileEvidence] = []
    for path in boundary.iter_files(root):
        out.append(read_evidence(root, path))
    return out
