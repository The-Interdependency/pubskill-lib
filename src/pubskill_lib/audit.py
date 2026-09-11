"""Inspect CLI for pubskill-lib.

Usage:
    python -m pubskill_lib.audit PATH --out findings.json

v0.2 inspect only: read declared files, record identity, and flag evidenced
repository defects. It never installs target dependencies or runs target tests.
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from .schema import new_document, validate_document

README_NAMES = ("README.md", "readme.md", "README", "README.txt", "Readme.md")
WORKFLOW_SUFFIXES = (".yml", ".yaml")
TEST_RUNNER_PATTERN = re.compile(
    r"\b(pytest|python\s+-m\s+unittest|unittest|node\s+--test|npm\s+(test|run\s+test)"
    r"|yarn\s+test|pnpm\s+test|make\s+test|cargo\s+test|go\s+test|tox)\b",
    re.IGNORECASE,
)
ECHO_OR_NOOP_PATTERN = re.compile(r"\b(echo|true|exit\s+0|printf)\b", re.IGNORECASE)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
PIN_PATTERN = re.compile(r"`([0-9a-f]{40})`")
LOCAL_SCRIPT_INTERPRETERS = {"node", "python", "python3", "bash", "sh"}
NON_FILE_MODES = {"-c", "-m", "-e", "--eval", "--print", "-p"}


class _Sink:
    def __init__(self):
        self.items = []

    def add(self, surface, claim, evidence, klass="defect", owner="repository"):
        self.items.append(
            {
                "id": None,
                "surface": surface,
                "claim": claim,
                "evidence": evidence,
                "class": klass,
                "owner": owner,
                "verified": False,
            }
        )

    def finalize(self):
        for index, item in enumerate(self.items, 1):
            item["id"] = f"F{index:03d}"
        return self.items


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _git_identity(target):
    if not (target / ".git").exists():
        return None

    def run(args):
        try:
            result = subprocess.run(
                ["git", "-C", str(target), *args],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    commit = run(["rev-parse", "HEAD"]) or "hmmm"
    remote = run(["remote", "get-url", "origin"]) or "hmmm"
    status = run(["status", "--porcelain"])
    return commit, remote, bool(status)


def _check_readme_links(target, sink):
    for name in README_NAMES:
        readme = target / name
        text = _read_text(readme)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for dest in MARKDOWN_LINK_PATTERN.findall(line):
                dest = dest.strip()
                if not dest or dest.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                local = dest.split("#", 1)[0]
                if local.startswith("/"):
                    continue
                resolved = (readme.parent / local).resolve()
                try:
                    resolved.relative_to(target.resolve())
                except ValueError:
                    sink.add("docs", f"README link escapes repository: {dest}", f"{name}:{lineno}")
                    continue
                if not resolved.exists():
                    sink.add("docs", f"README links to {dest}", f"{name}:{lineno}")


def _check_ci_workflows(target, sink):
    workflows_dir = target / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return
    for workflow in sorted(workflows_dir.iterdir()):
        if workflow.suffix not in WORKFLOW_SUFFIXES:
            continue
        text = _read_text(workflow) or ""
        claims_tests = "test" in workflow.name.lower() or "test" in text.lower()
        if not claims_tests:
            continue
        has_runner = bool(TEST_RUNNER_PATTERN.search(text))
        has_noop = bool(ECHO_OR_NOOP_PATTERN.search(text))
        if not has_runner and has_noop:
            sink.add(
                "ci",
                f"workflow {workflow.name} claims tests but only echoes",
                f".github/workflows/{workflow.name}",
            )


def _module_exists(target, module):
    relative = Path(*module.split("."))
    candidates = (
        target / "src" / relative.with_suffix(".py"),
        target / "src" / relative / "__init__.py",
        target / relative.with_suffix(".py"),
        target / relative / "__init__.py",
    )
    return any(candidate.exists() for candidate in candidates)


def _check_pyproject_scripts(target, sink):
    pyproject = target / "pyproject.toml"
    text = _read_text(pyproject)
    if text is None:
        return
    try:
        import tomllib
        data = tomllib.loads(text)
    except (ImportError, ValueError):
        return
    scripts = (data.get("project") or {}).get("scripts") or {}
    for name in sorted(scripts):
        entry = str(scripts[name])
        module = entry.split(":", 1)[0].strip()
        if module and not _module_exists(target, module):
            sink.add(
                "deps",
                f"declared script {name} points to missing module {module}",
                "pyproject.toml [project.scripts]",
            )


def _local_script_targets(command):
    """Yield direct local script operands without mistaking interpreter flags for paths."""
    for segment in re.split(r"\s*(?:&&|;|\|)\s*", command):
        if not segment.strip():
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if not tokens or tokens[0] not in LOCAL_SCRIPT_INTERPRETERS:
            continue
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token in NON_FILE_MODES:
                break
            if token.startswith("-"):
                index += 1
                continue
            yield token
            break


def _check_package_scripts(target, sink):
    package = target / "package.json"
    text = _read_text(package)
    if text is None:
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        sink.add("deps", "package.json is not valid JSON", "package.json")
        return
    if not isinstance(data, dict):
        sink.add("deps", "package.json top level is not an object", "package.json")
        return
    scripts = data.get("scripts") or {}
    if not isinstance(scripts, dict):
        return
    for name, command in sorted(scripts.items()):
        if not isinstance(command, str):
            continue
        for raw_path in _local_script_targets(command):
            raw_path = raw_path.strip('"\'')
            if raw_path.startswith("/") or "://" in raw_path:
                continue
            local = (target / raw_path).resolve()
            try:
                local.relative_to(target.resolve())
            except ValueError:
                sink.add("deps", f"package script {name} escapes repository via {raw_path}", "package.json [scripts]")
                continue
            if not local.exists():
                sink.add(
                    "deps",
                    f"package script {name} points to missing local file {raw_path}",
                    "package.json [scripts]",
                )


def _read_source_pin():
    root = Path(__file__).resolve().parents[2]
    text = _read_text(root / "SOURCE.md") or ""
    match = PIN_PATTERN.search(text)
    return match.group(1) if match else "hmmm"


def audit_path(target_path, source_pin=None):
    target = Path(target_path)
    source_pin = source_pin or _read_source_pin()
    document = new_document(source_pin, target_path)

    identity = _git_identity(target)
    if identity is None:
        document["hmmm"].append("target has no .git directory; identity unresolved")
    else:
        document["target"]["commit"], document["target"]["remote"], document["target"]["dirty"] = identity

    surfaces = ["identity"]
    sink = _Sink()

    if any((target / name).exists() for name in README_NAMES):
        surfaces.append("docs")
        _check_readme_links(target, sink)

    if (target / ".github" / "workflows").is_dir():
        surfaces.append("ci")
        _check_ci_workflows(target, sink)

    has_pyproject = (target / "pyproject.toml").exists()
    has_package = (target / "package.json").exists()
    if has_pyproject or has_package:
        surfaces.append("deps")
        if has_pyproject:
            _check_pyproject_scripts(target, sink)
        if has_package:
            _check_package_scripts(target, sink)

    document["surfaces"] = surfaces
    document["findings"] = sink.finalize()
    validate_document(document)
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pubskill_lib.audit")
    parser.add_argument("path", help="local repository path to inspect")
    parser.add_argument("--out", required=True, help="findings.json output path")
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"pubskill_lib.audit: target does not exist: {target}", file=sys.stderr)
        return 3

    try:
        document = audit_path(target)
    except Exception as exc:
        print(f"pubskill_lib.audit: tool failure: {exc}", file=sys.stderr)
        return 3

    out = Path(args.out)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"pubskill_lib.audit: cannot write --out: {exc}", file=sys.stderr)
        return 3

    print(f"pubskill_lib.audit: wrote {out} ({len(document['findings'])} findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
