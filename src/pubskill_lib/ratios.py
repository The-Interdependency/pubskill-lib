"""Ratios engine: one output contract, many language adapters.

The engine owns the normalized output shape and the source-boundary
placement rules. Language-specific parsing lives in
``pubskill_lib.ratios_adapters`` behind one interface
(:class:`LanguageRatioAdapter`), so adding a language is a plugin operation
and never a change to this core.

Two concerns are deliberately separate:

* **Computation** — the adapter answers what the numbers are. If a language
  cannot faithfully compute one canonical metric yet, the adapter returns
  ``"hmmm"`` for that metric rather than approximating it under the same
  name.
* **Placement** — this core answers where the seal may legally go, using the
  adapter's ``opening_boundary`` facts (shebang, encoding header,
  language-required prologue). The seal never displaces a protected line.

Output contract (same for every adapter)::

    {"loc_comments": "N:M", "imports_exports": "N:M", "calls_definitions": "N:M"}

where any metric may be ``"hmmm"`` when unresolved for that language.
"""

from __future__ import annotations

import re
from pathlib import Path

RATIO_IDS = ("loc_comments", "imports_exports", "calls_definitions")
SHEBANG_RE = re.compile(r"^#!.*$")
_UNRESOLVED = "hmmm"


class LanguageRatioAdapter:
    """Per-language contract.

    Adapters implement parsing for their syntax and return the same
    normalized metric meanings. ``opening_boundary`` returns the indices of
    lines that must legally stay above the opening seal (shebang, encoding
    headers, required prologues); it does **not** decide the seal position —
    the engine does that from these facts.
    """

    name: str = "base"
    extensions: tuple[str, ...] = ()
    marker: str = "#"

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def opening_boundary(self, lines: list[str]) -> list[int]:
        """Indices of lines that must stay above the opening seal."""
        if lines and SHEBANG_RE.match(lines[0].rstrip()):
            return [0]
        return []

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        raise NotImplementedError

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        raise NotImplementedError

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        raise NotImplementedError

    def find_internal_dependencies(self, path: Path, repo_files: set[Path]) -> set[str]:
        """Relative paths inside the repository this file depends on."""
        return set()

    def compute(self, text: str) -> dict[str, str]:
        lines = text.splitlines()
        code, comments = self.count_code_comments(lines)
        imports, exports = self.count_imports_exports(lines)
        calls, definitions = self.count_calls_definitions(lines)

        def pair(a: object, b: object) -> str:
            if a == _UNRESOLVED or b == _UNRESOLVED:
                return _UNRESOLVED
            return f"{a}:{b}"

        return {
            "loc_comments": pair(code, comments),
            "imports_exports": pair(imports, exports),
            "calls_definitions": pair(calls, definitions),
        }


def default_adapter_for(path: Path) -> LanguageRatioAdapter | None:
    """Fallback: shebang-aware placement but no computation."""
    for adapter in _registry():
        if adapter.detect(path):
            return adapter
    return None


class RatiosEngine:
    """Registry-backed computer. The invariant is the contract, not reuse."""

    def __init__(self, adapters: list[LanguageRatioAdapter] | None = None):
        self.adapters = list(adapters if adapters is not None else _registry())

    def adapter_for(self, path: Path) -> LanguageRatioAdapter | None:
        for adapter in self.adapters:
            if adapter.detect(path):
                return adapter
        return None

    def compute(self, path: Path, text: str) -> dict[str, str]:
        adapter = self.adapter_for(path)
        if adapter is None:
            return {key: _UNRESOLVED for key in RATIO_IDS}
        return adapter.compute(text)

    def place(self, text: str, marker: str, values: dict[str, str], path: Path | None = None) -> tuple[str, bool]:
        adapter = self.adapter_for(path) if path is not None else None
        return place_ratios(text, marker, values, adapter)


def _registry() -> list[LanguageRatioAdapter]:
    """Lazy import so adapters can subclass the base defined here."""
    from . import ratios_adapters  # noqa: PLC0415 - lazy to avoid circular import

    return list(ratios_adapters.ALL)


def _ratios_line_re(marker: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(marker)}\s*ratios:\s*(?P<body>.+?)\s*$")


def render_ratios_line(marker: str, values: dict[str, str]) -> str:
    """Render the single named-form ratios comment line."""
    body = " ".join(f"{key}={values.get(key, _UNRESOLVED)}" for key in RATIO_IDS)
    return f"{marker} ratios: {body}"


def strip_ratios_lines(text: str, marker: str) -> list[str]:
    """Return the file's lines with every ratios line removed."""
    line_re = _ratios_line_re(marker)
    return [line for line in text.splitlines() if not line_re.match(line.rstrip())]


def opening_index(lines: list[str], adapter: LanguageRatioAdapter | None) -> int:
    """Index where the opening seal may legally go.

    The seal goes immediately after the last protected prologue line. With no
    adapter, the default rule applies: a shebang stays first and the seal
    follows it.
    """
    if adapter is not None:
        protected = adapter.opening_boundary(lines)
    else:
        protected = [0] if lines and SHEBANG_RE.match(lines[0].rstrip()) else []
    return max(protected, default=-1) + 1


def place_ratios(
    text: str,
    marker: str,
    values: dict[str, str],
    adapter: LanguageRatioAdapter | None = None,
) -> tuple[str, bool]:
    """Insert the ratios bookends without displacing protected lines.

    Returns ``(new_text, changed)``. Existing ratios lines are removed and
    re-placed. The closing line is the last non-blank line.
    """
    line_re = _ratios_line_re(marker)
    lines = [raw for raw in text.splitlines() if not line_re.match(raw.rstrip())]
    opening = render_ratios_line(marker, values)

    lines.insert(opening_index(lines, adapter), opening)

    while lines and lines[-1].strip() == "":
        lines.pop()
    lines.append(opening)

    new_text = "\n".join(lines)
    if lines:
        new_text += "\n"
    return new_text, new_text != text


def compute_for(path: Path, text: str, marker: str | None = None) -> dict[str, str]:
    """Compute ratio values for a path through the registry, or ``hmmm``."""
    return RatiosEngine().compute(path, text)


def compute_python(text: str, marker: str = "#") -> dict[str, str]:
    """Reference Python computer, kept for compatibility with earlier callers."""
    from . import ratios_adapters  # noqa: PLC0415

    return ratios_adapters.PythonAdapter().compute(text)
