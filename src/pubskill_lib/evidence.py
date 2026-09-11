"""Evidence engine: inventory actual code before describing it.

Language comment markers and entry grammar are loaded from the vendored
canonical msdmd parser; this module does not maintain a second dialect.
``sha256`` is the stable source evidence hash: generated examiner NARRATIVE
blocks and RATIOS seals are excluded so the examiner cannot make its own
evidence stale. ``raw_sha256`` retains the literal file-content hash.
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
def _msdmd_parser():
    """Load the pinned repo-local canonical msdmd parser module."""
    repo = Path(__file__).resolve().parents[2]
    parser_path = repo / ".agents" / "skills" / "msdmd" / "parsers" / "universal.py"
    spec = importlib.util.spec_from_file_location("pubskill_lib._vendored_msdmd", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load vendored msdmd parser: {parser_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _comment_markers() -> dict[str, str]:
    """Load COMMENT_MARKERS from the pinned repo-local msdmd parser."""
    markers = getattr(_msdmd_parser(), "COMMENT_MARKERS", {})
    return dict(markers) if isinstance(markers, dict) else {}


def source_text(text: str, marker: str | None) -> str:
    """Return source text with complete generated NARRATIVE/RATIOS metadata removed.

    Trailing blank lines are normalized because RATIOS placement already removes
    them. Incomplete NARRATIVE fences are preserved rather than guessed away.
    """
    if marker is None:
        return text

    start = f"{marker} === NARRATIVE ==="
    end = f"{marker} === END NARRATIVE ==="
    lines = text.splitlines()
    kept: list[str] = []
    index = 0

    while index < len(lines):
        raw = lines[index]
        if raw.rstrip() == start:
            close = index + 1
            while close < len(lines) and lines[close].rstrip() != end:
                close += 1
            if close < len(lines):
                index = close + 1
                continue
        if not _RATIOS_LINE_RE.match(raw.rstrip()):
            kept.append(raw)
        index += 1

    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept) + ("\n" if kept else "")


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
    raw_sha256: str = ""
    size: int = 0
    executable: bool = False
    hmmm: list[str] = field(default_factory=list)


def _block_names(text: str, marker: str) -> list[str]:
    """Return distinct declared block names; canonical parser owns entry grammar."""
    m = re.escape(marker)
    start_re = re.compile(rf"^{m} === (?P<name>[A-Z_]+) ===\s*$", re.MULTILINE)
    return list(dict.fromkeys(match.group("name") for match in start_re.finditer(text)))


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

    raw_encoded = text.encode("utf-8", errors="replace")
    stable_encoded = source_text(text, marker).encode("utf-8", errors="replace")
    item.raw_sha256 = hashlib.sha256(raw_encoded).hexdigest()
    item.sha256 = hashlib.sha256(stable_encoded).hexdigest()
    item.size = len(raw_encoded)
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
        parser = _msdmd_parser()
        for name in _block_names(text, marker):
            entries = parser.parse_text(text, name, marker)
            item.msdmd_blocks[name] = entries
        item.narrative_entries = item.msdmd_blocks.get("NARRATIVE", [])
    else:
        item.hmmm.append(f"unsupported language for msdmd: .{language}")
    return item


def inventory(root: Path) -> list[FileEvidence]:
    root = boundary.assert_inside(root, root)
    return [read_evidence(root, path) for path in boundary.iter_files(root)]
