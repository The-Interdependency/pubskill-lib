"""msdmd NARRATIVE writer: generated explanation is descriptive evidence.

NARRATIVE placement shares the language opening-boundary rules used by the
RATIOS engine so metadata never displaces an interpreter or protected source
prologue.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import ratios

NARRATIVE_BLOCK = "NARRATIVE"


def _fence_re(marker: str) -> re.Pattern[str]:
    m = re.escape(marker)
    return re.compile(
        rf"^{m} === {NARRATIVE_BLOCK} ===\s*$.*?^{m} === END {NARRATIVE_BLOCK} ===\s*$",
        re.MULTILINE | re.DOTALL,
    )


def _block_lines(marker: str, entry: dict[str, str]) -> list[str]:
    lines = [f"{marker} === {NARRATIVE_BLOCK} ==="]
    for key, value in entry.items():
        lines.append(f"{marker} {key}: {value}")
    lines.append(f"{marker} === END {NARRATIVE_BLOCK} ===")
    return lines


def narrative_id(sha256: str) -> str:
    return f"examiner_{sha256[:16]}"


def upsert_narrative(
    text: str,
    marker: str,
    entry: dict[str, str],
    path: Path | None = None,
) -> tuple[str, bool]:
    """Replace NARRATIVE blocks without crossing the protected opening boundary."""
    body = _fence_re(marker).sub("", text).rstrip("\n")
    block = "\n".join(_block_lines(marker, entry))
    lines = body.splitlines()

    adapter = ratios.RatiosEngine().adapter_for(path) if path is not None else None
    insert_at = ratios.opening_index(lines, adapter)
    ratios_prefix = f"{marker} ratios:"
    if insert_at < len(lines) and lines[insert_at].lstrip().startswith(ratios_prefix):
        insert_at += 1

    lines.insert(insert_at, block)
    new_text = "\n".join(lines) + "\n"
    return new_text, new_text != text


def write_text_safely(path: Path, new_text: str) -> None:
    """Write text without changing the file's executable bit."""
    mode = None
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        pass
    path.write_text(new_text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)
