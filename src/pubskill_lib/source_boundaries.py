"""Identify examiner metadata only at its reserved source placement boundaries.

Fence-shaped text elsewhere remains source data, including inside multiline
strings. Entry parsing remains owned by the packaged canonical msdmd parser.
"""
from __future__ import annotations

import re


def opening_index(lines, adapter=None):
    if adapter is not None:
        protected = adapter.opening_boundary(lines)
    else:
        protected = [0] if lines and lines[0].startswith("#!") else []
    return max(protected, default=-1) + 1


def metadata_indices(lines, marker, adapter=None):
    """Return reserved RATIOS indices and one complete opening NARRATIVE span."""
    ratio_line = re.compile(rf"^{re.escape(marker)}\s*ratios:\s*.+?\s*$")
    ratios = set()
    opening = opening_index(lines, adapter)
    if opening < len(lines) and ratio_line.fullmatch(lines[opening]):
        ratios.add(opening)
        opening += 1
    closing = len(lines) - 1
    while closing >= 0 and not lines[closing].strip():
        closing -= 1
    if closing >= 0 and ratio_line.fullmatch(lines[closing]):
        ratios.add(closing)
    narrative = set()
    if opening < len(lines) and lines[opening].rstrip() == f"{marker} === NARRATIVE ===":
        for index in range(opening + 1, len(lines)):
            if not lines[index].startswith(marker):
                break
            if lines[index].rstrip() == f"{marker} === END NARRATIVE ===":
                narrative.update(range(opening, index + 1))
                break
    return ratios, narrative
