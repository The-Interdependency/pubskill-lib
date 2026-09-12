"""Evidence engine: inventory actual code before describing it.

Language comment markers and entry grammar are loaded from the packaged copy of
the pinned canonical msdmd parser; this module does not maintain a second
dialect. ``sha256`` is the stable source evidence hash: generated examiner
NARRATIVE blocks and RATIOS seals are excluded when the source can be decoded.
``raw_sha256`` is always the literal file-byte hash.
"""

from __future__ import annotations

import hashlib
import io
import re
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

from . import _msdmd_universal as _canonical_msdmd
from . import boundary

SHEBANG_RE = re.compile(r"^#!.*$")
_RATIOS_LINE_RE = re.compile(r"^(?:#|//|--|%|;|!|'|\*>)\s*ratios:\s*(.+?)\s*$")
_PYTHON_SUFFIXES = {".py", ".pyw", ".pyi"}


def _msdmd_parser():
    """Return the packaged, source-pinned canonical msdmd parser module."""
    return _canonical_msdmd


def _comment_markers() -> dict[str, str]:
    """Load COMMENT_MARKERS from the packaged canonical msdmd parser."""
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
    encoding: str | None = "utf-8"
    hmmm: list[str] = field(default_factory=list)


def _block_names(text: str, marker: str) -> list[str]:
    """Return distinct declared block names; canonical parser owns entry grammar."""
    m = re.escape(marker)
    start_re = re.compile(rf"^{m} === (?P<name>[A-Z_]+) ===\s*$", re.MULTILINE)
    return list(dict.fromkeys(match.group("name") for match in start_re.finditer(text)))


def _decode_source(path: Path, raw: bytes) -> tuple[str | None, str | None, str | None]:
    """Decode source without changing byte identity; honor Python coding cookies."""
    if path.suffix.lower() in _PYTHON_SUFFIXES:
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            return raw.decode(encoding), encoding, None
        except (LookupError, SyntaxError, UnicodeDecodeError) as exc:
            return None, None, f"source encoding unresolved: {exc}"
    try:
        return raw.decode("utf-8"), "utf-8", None
    except UnicodeDecodeError as exc:
        return None, None, f"source encoding unresolved: {exc}"


def read_evidence(root: Path, path: Path) -> FileEvidence:
    root = Path(root).resolve()
    rel = str(path.relative_to(root))
    marker = _comment_markers().get(path.suffix.lower())
    language = path.suffix.lower().lstrip(".") or "unknown"
    item = FileEvidence(path=rel, language=language, marker=marker)
    try:
        raw = path.read_bytes()
    except OSError:
        item.hmmm.append("unreadable file")
        return item

    item.raw_sha256 = hashlib.sha256(raw).hexdigest()
    item.size = len(raw)
    try:
        item.executable = bool(path.stat().st_mode & 0o111)
    except OSError:
        pass

    text, item.encoding, decode_hmmm = _decode_source(path, raw)
    if text is None:
        item.sha256 = item.raw_sha256
        item.marker = None
        item.hmmm.append(decode_hmmm or "source encoding unresolved")
        item.hmmm.append("metadata-excluding source hash unavailable; mutation disabled")
        return item

    stable_encoded = source_text(text, marker).encode("utf-8")
    item.sha256 = hashlib.sha256(stable_encoded).hexdigest()

    first_line = text.splitlines()[0].rstrip() if text.splitlines() else ""
    if SHEBANG_RE.match(first_line):
        item.shebang = first_line

    if marker is not None:
        for raw_line in text.splitlines():
            if _RATIOS_LINE_RE.match(raw_line.rstrip()):
                item.ratios_lines.append(raw_line.rstrip())
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
