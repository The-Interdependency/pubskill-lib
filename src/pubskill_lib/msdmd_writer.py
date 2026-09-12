"""msdmd NARRATIVE writer: generated explanation is descriptive evidence.

NARRATIVE placement shares the language opening-boundary rules used by the
RATIOS engine so metadata never displaces an interpreter or protected source
prologue.
"""

from __future__ import annotations

from pathlib import Path

from . import ratios

NARRATIVE_BLOCK = "NARRATIVE"


def _block_lines(marker: str, entry: dict[str, str]) -> list[str]:
    lines = [f"{marker} === {NARRATIVE_BLOCK} ==="]
    for key, value in entry.items():
        lines.append(f"{marker} {key}: {value}")
    lines.append(f"{marker} === END {NARRATIVE_BLOCK} ===")
    return lines


def _without_narrative_lines(text: str, marker: str) -> list[str]:
    """Remove complete NARRATIVE blocks without creating phantom blank lines."""
    start = f"{marker} === {NARRATIVE_BLOCK} ==="
    end = f"{marker} === END {NARRATIVE_BLOCK} ==="
    lines = text.splitlines()
    kept: list[str] = []
    index = 0

    while index < len(lines):
        if lines[index].rstrip() == start:
            close = index + 1
            while close < len(lines) and lines[close].rstrip() != end:
                close += 1
            if close < len(lines):
                index = close + 1
                continue
        kept.append(lines[index])
        index += 1

    while kept and not kept[-1].strip():
        kept.pop()
    return kept


def narrative_id(sha256: str) -> str:
    return f"examiner_{sha256[:16]}"


def upsert_narrative(
    text: str,
    marker: str,
    entry: dict[str, str],
    path: Path | None = None,
) -> tuple[str, bool]:
    """Replace NARRATIVE blocks without crossing the protected opening boundary."""
    lines = _without_narrative_lines(text, marker)
    block = "\n".join(_block_lines(marker, entry))

    adapter = ratios.RatiosEngine().adapter_for(path) if path is not None else None
    insert_at = ratios.opening_index(lines, adapter)
    ratios_prefix = f"{marker} ratios:"
    if insert_at < len(lines) and lines[insert_at].lstrip().startswith(ratios_prefix):
        insert_at += 1

    lines.insert(insert_at, block)
    new_text = "\n".join(lines) + ("\n" if lines else "")
    return new_text, new_text != text


def write_text_safely(path: Path, new_text: str, encoding: str = "utf-8") -> None:
    """Preserve the source encoding and mode; encode before opening for writing."""
    encoded = new_text.encode(encoding)
    mode = None
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        pass
    path.write_bytes(encoded)
    if mode is not None:
        path.chmod(mode)
