"""msdmd NARRATIVE writer: generated explanation is descriptive evidence.

NARRATIVE placement shares the language opening-boundary rules used by the
RATIOS engine so metadata never displaces an interpreter or protected source
prologue.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

from . import ratios
from . import source_boundaries

NARRATIVE_BLOCK = "NARRATIVE"


def _block_lines(marker: str, entry: dict[str, str]) -> list[str]:
    lines = [f"{marker} === {NARRATIVE_BLOCK} ==="]
    for key, value in entry.items():
        lines.append(f"{marker} {key}: {value}")
    lines.append(f"{marker} === END {NARRATIVE_BLOCK} ===")
    return lines


def _without_narrative_lines(text: str, marker: str, adapter=None) -> list[str]:
    """Remove complete NARRATIVE blocks without creating phantom blank lines."""
    lines = text.splitlines()
    _, indices = source_boundaries.metadata_indices(lines, marker, adapter)
    kept = [line for index, line in enumerate(lines) if index not in indices]

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
    adapter = ratios.RatiosEngine().adapter_for(path) if path is not None else None
    lines = _without_narrative_lines(text, marker, adapter)
    block = "\n".join(_block_lines(marker, entry))

    insert_at = ratios.opening_index(lines, adapter)
    ratios_prefix = f"{marker} ratios:"
    if insert_at < len(lines) and lines[insert_at].lstrip().startswith(ratios_prefix):
        insert_at += 1

    lines.insert(insert_at, block)
    new_text = "\n".join(lines) + ("\n" if lines else "")
    return new_text, new_text != text


class SourceChangedError(RuntimeError):
    """The live source no longer matches the inventoried bytes."""


def write_text_safely(path: Path, new_text: str, encoding: str = "utf-8", *, expected_raw: bytes | None = None) -> None:
    """Preserve the source encoding and mode; encode before opening for writing."""
    encoded = new_text.encode(encoding)
    mode = None
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        pass
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".examiner-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        if mode is not None:
            temporary.chmod(mode)
        if expected_raw is not None and (path.is_symlink() or path.read_bytes() != expected_raw):
            raise SourceChangedError("source changed before metadata publication")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
