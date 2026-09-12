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


def write_text_safely(path: Path, new_text: str, encoding: str = "utf-8", *, expected_raw: bytes | None = None) -> Path:
    """Publish without replacing a live name; retain the original inode.

    There is a short absent-name interval. Publication uses link's atomic
    no-replace guarantee. Open writers keep their original inode in recovery
    storage, which is deliberately never deleted by this operation.
    """
    encoded = new_text.encode(encoding)
    if path.is_symlink():
        raise SourceChangedError("source became a symlink; mutation skipped")
    raw = path.read_bytes() if expected_raw is None else expected_raw
    mode = path.stat().st_mode & 0o777
    # A fresh private directory prevents a preexisting recovery path from
    # redirecting writes. The caller reports its path; inventory skips it.
    recovery = Path(tempfile.mkdtemp(prefix=".examiner-originals-", dir=path.parent))
    original = recovery / "original"
    candidate = recovery / "candidate"
    candidate.write_bytes(encoded)
    candidate.chmod(mode)
    moved = False
    try:
        if path.is_symlink() or path.read_bytes() != raw:
            raise SourceChangedError("source changed before metadata publication")
        os.rename(path, original)
        moved = True
        if original.is_symlink() or original.read_bytes() != raw:
            raise SourceChangedError(f"source changed during publication; preserved at {original}")
        try:
            os.link(candidate, path)  # Atomic create-if-absent; never replace a competing edit.
        except FileExistsError as error:
            raise SourceChangedError(f"competing source preserved; prior inode at {original}") from error
        if original.read_bytes() != raw:
            raise SourceChangedError(f"open writer changed original inode; inspect preserved source at {original}")
        return original
    except BaseException as failure:
        if moved:
            try:
                os.link(original, path, follow_symlinks=False)
            except FileExistsError:
                pass  # Preserve the live name and the recovery inode independently.
            except OSError as error:
                raise SourceChangedError(f"source retained at {original}; restore failed: {error}") from error
            if isinstance(failure, OSError):
                raise OSError(f"publication failed; original retained at {original}: {failure}") from failure
        raise
    finally:
        candidate.unlink(missing_ok=True)
        if not moved:
            recovery.rmdir()
