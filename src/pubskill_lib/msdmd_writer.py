"""msdmd NARRATIVE writer: generated explanation is descriptive evidence.

The NARRATIVE block is a normal msdmd fenced block, never a CONTRACT, CHECK,
CAPABILITY, OWNERS, DOCS, or other normative declaration. It carries the
content hash that produced it so stale narrative can be detected.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

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
    """Stable, refactor-safe entry id derived from the evidence hash."""
    return f"examiner_{sha256[:16]}"


def upsert_narrative(text: str, marker: str, entry: dict[str, str]) -> tuple[str, bool]:
    """Replace any existing NARRATIVE blocks with ``entry``, keeping the
    shebang first and the ratios bookends where they were."""
    fence = _fence_re(marker)
    body = fence.sub("", text).rstrip("\n")
    block = "\n".join(_block_lines(marker, entry))

    lines = body.splitlines()
    ratios_prefix = f"{marker} ratios:"
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
        if len(lines) > 1 and lines[1].lstrip().startswith(ratios_prefix):
            insert_at = 2
    elif lines and lines[0].lstrip().startswith(ratios_prefix):
        insert_at = 1
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
