"""Language adapters for the ratios engine.

Each adapter implements the :class:`LanguageRatioAdapter` contract from
``pubskill_lib.ratios`` using its language's syntax, and returns the same
normalized meanings:

* ``count_code_comments`` -> code lines : comment+docstring lines
* ``count_imports_exports`` -> consumed : declared (per-file stand-ins)
* ``count_calls_definitions`` -> call sites : definitions

If a metric cannot be computed faithfully for a language, that adapter
returns ``"hmmm"`` for the affected side and the engine renders the whole
metric as ``hmmm`` rather than approximating it under the same name.

Adding a language means adding one class here and appending it to ``ALL``.
"""

from __future__ import annotations

import re
from pathlib import Path

from .ratios import LanguageRatioAdapter, SHEBANG_RE

_UNRESOLVED = "hmmm"

_CALL_RE = re.compile(r"\b[a-zA-Z_]\w*\s*\(")


def _strip_own_seal(lines: list[str], marker: str) -> list[str]:
    """Adapters count the source, not the seal lines that measure it."""
    seal = re.compile(rf"^{re.escape(marker)}\s*ratios:\s*")
    return [line for line in lines if not seal.match(line.rstrip())]


class PythonAdapter(LanguageRatioAdapter):
    name = "python"
    extensions = (".py",)
    marker = "#"

    _IMPORT_RE = re.compile(r"^\s*(import\s+\S+|from\s+\S+\s+import\b)")
    _TOP_DEF_RE = re.compile(r"^(def\s+\w+|class\s+\w+|async\s+def\s+\w+)")
    _CODING_RE = re.compile(r"^\s*#.*coding[:=]\s*[-\w.]+")

    def opening_boundary(self, lines: list[str]) -> list[int]:
        protected: list[int] = []
        if lines and SHEBANG_RE.match(lines[0].rstrip()):
            protected.append(0)
            candidates = (1, 2)
        else:
            candidates = (0, 1)
        for index in candidates:
            if index < len(lines) and self._CODING_RE.match(lines[index]):
                protected.append(index)
        return protected

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        code = comment = 0
        in_triple = False
        triple = None
        for raw in _strip_own_seal(lines, self.marker):
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
        return code, comment

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        imports = sum(1 for raw in _strip_own_seal(lines, self.marker) if self._IMPORT_RE.match(raw))
        exports = sum(1 for raw in _strip_own_seal(lines, self.marker) if self._TOP_DEF_RE.match(raw))
        return imports, exports

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        definitions = sum(1 for raw in stripped if self._TOP_DEF_RE.match(raw))
        calls = sum(1 for raw in stripped if _CALL_RE.search(raw) and not self._TOP_DEF_RE.match(raw))
        return calls, definitions

    def find_internal_dependencies(self, path: Path, repo_files: set[Path]) -> set[str]:
        stems = {p.stem: str(p) for p in repo_files}
        found: set[str] = set()
        try:
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = re.match(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", raw)
                if not match:
                    continue
                module = (match.group(1) or match.group(2)).split(".")[0]
                if module in stems:
                    found.add(stems[module])
        except OSError:
            pass
        return found


class JavaScriptTypeScriptAdapter(LanguageRatioAdapter):
    name = "javascript-typescript"
    extensions = (".ts", ".tsx", ".js", ".jsx", ".mjs")
    marker = "//"

    _IMPORT_RE = re.compile(r"^\s*(import\b|export\s+.*\bfrom\b|require\s*\()")
    _EXPORT_RE = re.compile(r"^\s*export\b")
    _DEF_RE = re.compile(r"^\s*(export\s+)?(default\s+)?(function\s+\w+|class\s+\w+|(const|let|var)\s+\w+\s*=)")

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        code = comment = 0
        in_block = False
        for raw in _strip_own_seal(lines, self.marker):
            line = raw.strip()
            if not line:
                continue
            if in_block:
                comment += 1
                if "*/" in raw:
                    in_block = False
            elif line.startswith("/*"):
                comment += 1
                if "*/" not in raw[2:]:
                    in_block = True
            elif line.startswith("//"):
                comment += 1
            else:
                code += 1
        return code, comment

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        imports = sum(1 for raw in stripped if self._IMPORT_RE.match(raw))
        exports = sum(1 for raw in stripped if self._EXPORT_RE.match(raw))
        return imports, exports

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        definitions = sum(1 for raw in stripped if self._DEF_RE.match(raw))
        calls = sum(1 for raw in stripped if _CALL_RE.search(raw) and not self._DEF_RE.match(raw))
        return calls, definitions

    def find_internal_dependencies(self, path: Path, repo_files: set[Path]) -> set[str]:
        stems = {p.stem: str(p) for p in repo_files}
        found: set[str] = set()
        try:
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = re.match(r"""^\s*(?:import\s+.*?from\s*['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\))""", raw)
                if not match:
                    continue
                spec = match.group(1) or match.group(2) or ""
                if spec.startswith("."):
                    stem = Path(spec).stem
                    if stem in stems:
                        found.add(stems[stem])
        except OSError:
            pass
        return found


class CppAdapter(LanguageRatioAdapter):
    """C and C++.

    ``imports_exports`` is unresolved: C/C++ have no faithful module-export
    declaration, so the adapter returns ``hmmm`` instead of approximating.
    """

    name = "c-cpp"
    extensions = (".c", ".cc", ".cpp", ".h", ".hpp")
    marker = "//"

    _INCLUDE_RE = re.compile(r"^\s*#\s*include\b")
    _FUNC_DEF_RE = re.compile(r"^[\w:*&<>\s]+\s+\w+\s*\([^;]*\)\s*\{")

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        code = comment = 0
        in_block = False
        for raw in _strip_own_seal(lines, self.marker):
            line = raw.strip()
            if not line:
                continue
            if in_block:
                comment += 1
                if "*/" in raw:
                    in_block = False
            elif line.startswith("/*"):
                comment += 1
                if "*/" not in raw[2:]:
                    in_block = True
            elif line.startswith("//"):
                comment += 1
            else:
                code += 1
        return code, comment

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        imports = sum(1 for raw in _strip_own_seal(lines, self.marker) if self._INCLUDE_RE.match(raw))
        return imports, _UNRESOLVED

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        definitions = sum(1 for raw in stripped if self._FUNC_DEF_RE.match(raw))
        calls = sum(1 for raw in stripped if _CALL_RE.search(raw) and not self._FUNC_DEF_RE.match(raw))
        return calls, definitions


class JavaAdapter(LanguageRatioAdapter):
    name = "java"
    extensions = (".java",)
    marker = "//"

    _IMPORT_RE = re.compile(r"^\s*import\b")
    _PUBLIC_TYPE_RE = re.compile(r"^\s*public\s+(class|interface|enum|record)\s+\w+")
    _TYPE_RE = re.compile(r"^\s*(class|interface|enum|record)\s+\w+")
    _METHOD_RE = re.compile(r"^\s*(public|private|protected|static|final|synchronized|abstract|native|default|\s)*[\w<>\[\]]+\s+\w+\s*\([^;]*\)\s*\{")

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        code = comment = 0
        in_block = False
        for raw in _strip_own_seal(lines, self.marker):
            line = raw.strip()
            if not line:
                continue
            if in_block:
                comment += 1
                if "*/" in raw:
                    in_block = False
            elif line.startswith("/*"):
                comment += 1
                if "*/" not in raw[2:]:
                    in_block = True
            elif line.startswith("//"):
                comment += 1
            else:
                code += 1
        return code, comment

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        imports = sum(1 for raw in stripped if self._IMPORT_RE.match(raw))
        exports = sum(1 for raw in stripped if self._PUBLIC_TYPE_RE.match(raw))
        return imports, exports

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        definitions = sum(1 for raw in stripped if self._TYPE_RE.match(raw) or self._METHOD_RE.match(raw))
        calls = sum(1 for raw in stripped if _CALL_RE.search(raw) and not (self._TYPE_RE.match(raw) or self._METHOD_RE.match(raw)))
        return calls, definitions

    def find_internal_dependencies(self, path: Path, repo_files: set[Path]) -> set[str]:
        # Java imports are package-qualified; resolving them to repo files
        # faithfully needs package-root knowledge this adapter does not have.
        return set()


class PerlAdapter(LanguageRatioAdapter):
    name = "perl"
    extensions = (".pl", ".pm")
    marker = "#"

    _USE_RE = re.compile(r"^\s*(use|require)\s+[\w:]+")
    _SUB_RE = re.compile(r"^\s*sub\s+\w+")
    _EXPORT_NAMES_RE = re.compile(r"@EXPORT(?:_OK)?\s*=\s*qw\((.*?)\)")

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        code = comment = 0
        for raw in _strip_own_seal(lines, self.marker):
            if not raw.strip():
                continue
            if raw.lstrip().startswith("#"):
                comment += 1
            else:
                code += 1
        return code, comment

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        imports = sum(1 for raw in stripped if self._USE_RE.match(raw))
        exports = 0
        for raw in stripped:
            match = self._EXPORT_NAMES_RE.search(raw)
            if match:
                exports += len(match.group(1).split())
        return imports, exports

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        definitions = sum(1 for raw in stripped if self._SUB_RE.match(raw))
        calls = sum(1 for raw in stripped if _CALL_RE.search(raw) and not self._SUB_RE.match(raw))
        return calls, definitions


class RustAdapter(LanguageRatioAdapter):
    name = "rust"
    extensions = (".rs",)
    marker = "//"

    _USE_RE = re.compile(r"^\s*(use\b|extern\s+crate\b)")
    _PUB_RE = re.compile(r"^\s*pub\s+(fn|struct|enum|trait|mod|use|type|const|static)\b")
    _DEF_RE = re.compile(r"^\s*(pub\s+)?(fn|struct|enum|trait|impl|mod|type|const|static)\s+\w+")

    def count_code_comments(self, lines: list[str]) -> tuple[int, int]:
        code = comment = 0
        in_block = False
        for raw in _strip_own_seal(lines, self.marker):
            line = raw.strip()
            if not line:
                continue
            if in_block:
                comment += 1
                if "*/" in raw:
                    in_block = False
            elif line.startswith("/*"):
                comment += 1
                if "*/" not in raw[2:]:
                    in_block = True
            elif line.startswith("//"):
                comment += 1
            else:
                code += 1
        return code, comment

    def count_imports_exports(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        imports = sum(1 for raw in stripped if self._USE_RE.match(raw))
        exports = sum(1 for raw in stripped if self._PUB_RE.match(raw))
        return imports, exports

    def count_calls_definitions(self, lines: list[str]) -> tuple[int, int]:
        stripped = _strip_own_seal(lines, self.marker)
        definitions = sum(1 for raw in stripped if self._DEF_RE.match(raw))
        calls = sum(1 for raw in stripped if _CALL_RE.search(raw) and not self._DEF_RE.match(raw))
        return calls, definitions


ALL: list[LanguageRatioAdapter] = [
    PythonAdapter(),
    JavaScriptTypeScriptAdapter(),
    CppAdapter(),
    JavaAdapter(),
    PerlAdapter(),
    RustAdapter(),
]
