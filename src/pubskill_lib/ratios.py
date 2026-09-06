"""Shebang-aware RATIOS writer (named form) with Python computers.

The named form is the portable, per-file adaptation from canon msdmd:

    <marker> ratios: loc_comments=N:M imports_exports=N:M calls_definitions=N:M

Placement agrees with the canon parser: the shebang, when present, stays on
the literal first line and the ratios line follows immediately after it;
otherwise the ratios line is the first line. The closing line is the last
non-blank line. A ratios line above a shebang is a placement failure and is
repaired by re-placing.

Only Python has a shipped computer in this first release. Other languages
keep their values as ``hmmm`` rather than guessed numbers.
"""

from __future__ import annotations

import re
from pathlib import Path

RATIO_IDS = ("loc_comments", "imports_exports", "calls_definitions")
SHEBANG_RE = re.compile(r"^#!.*$")
_IMPORT_RE = re.compile(r"^\s*(import\s+\S+|from\s+\S+\s+import\b)")
_TOP_DEF_RE = re.compile(r"^(def\s+\w+|class\s+\w+|async\s+def\s+\w+)")
_CALL_RE = re.compile(r"\b[a-zA-Z_]\w*\s*\(")


def _ratios_line_re(marker: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(marker)}\s*ratios:\s*(?P<body>.+?)\s*$")


def render_ratios_line(marker: str, values: dict[str, str]) -> str:
    """Render the single named-form ratios comment line."""
    body = " ".join(f"{key}={values.get(key, 'hmmm')}" for key in RATIO_IDS)
    return f"{marker} ratios: {body}"


def strip_ratios_lines(text: str, marker: str) -> list[str]:
    """Return the file's lines with every ratios line removed."""
    line_re = _ratios_line_re(marker)
    return [line for line in text.splitlines() if not line_re.match(line.rstrip())]


def compute_python(text: str, marker: str = "#") -> dict[str, str]:
    """Compute the three named ratios for Python source.

    ``loc_comments`` is code lines : comment+docstring lines. The measuring
    lines themselves are excluded first so a ratio never inflates itself.
    """
    lines = strip_ratios_lines(text, marker)
    code = comment = 0
    in_triple = False
    triple = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if in_triple:
            comment += 1
            if triple in raw:
                in_triple = False
        elif line.startswith('"""') or line.startswith("'''"):
            comment += 1
            t = raw.strip()[:3]
            if raw.strip().count(t) < 2:
                in_triple = True
                triple = t
        elif line.startswith("#"):
            comment += 1
        else:
            code += 1

    imports = sum(1 for raw in lines if _IMPORT_RE.match(raw))
    defs = sum(1 for raw in lines if _TOP_DEF_RE.match(raw))
    calls = sum(1 for raw in lines if _CALL_RE.search(raw) and not _TOP_DEF_RE.match(raw))

    return {
        "loc_comments": f"{code}:{comment}",
        "imports_exports": f"{imports}:{defs}",
        "calls_definitions": f"{calls}:{defs}",
    }


def compute_for(path: Path, text: str, marker: str) -> dict[str, str]:
    """Compute ratio values, or ``hmmm`` for languages without a computer."""
    if path.suffix.lower() == ".py":
        return compute_python(text, marker)
    return {key: "hmmm" for key in RATIO_IDS}


def place_ratios(text: str, marker: str, values: dict[str, str]) -> tuple[str, bool]:
    """Insert the ratios bookends shebang-aware.

    Returns ``(new_text, changed)``. Existing ratios lines are removed and
    re-placed; the shebang is never displaced.
    """
    line_re = _ratios_line_re(marker)
    lines = [raw for raw in text.splitlines() if not line_re.match(raw.rstrip())]
    opening = render_ratios_line(marker, values)

    if lines and SHEBANG_RE.match(lines[0].rstrip()):
        lines.insert(1, opening)
    else:
        lines.insert(0, opening)

    while lines and lines[-1].strip() == "":
        lines.pop()
    lines.append(opening)

    new_text = "\n".join(lines)
    if lines:
        new_text += "\n"
    return new_text, new_text != text
