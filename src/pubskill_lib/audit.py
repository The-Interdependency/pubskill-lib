"""Inspect CLI for pubskill-lib.

Usage:
    python -m pubskill_lib.audit PATH --out findings.json

v0.2 inspect only: read declared files, record identity, and flag evidenced
repository defects. It never installs target dependencies or runs target tests.
"""

import argparse
import json
from importlib.resources import files
import re
import shlex
from urllib.parse import unquote, urlsplit
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
NON_FILE_MODES = {
    "node": {"-e", "--eval", "-p", "--print", "--run", "-h", "--help", "-v", "--version", "--v8-options", "--completion-bash"},
    "python": {"-c", "-m", "-h", "-?", "--help", "-V", "--version", "--help-env", "--help-xoptions", "--help-all"},
    "python3": {"-c", "-m", "-h", "-?", "--help", "-V", "--version", "--help-env", "--help-xoptions", "--help-all"},
    "bash": {"-c", "--help", "--version"},
    "sh": {"-c", "--help", "--version"},
}
BOOLEAN_OPTIONS = {
    "node": {"--trace-warnings", "--inspect", "--inspect-brk", "--inspect-wait", "--watch", "--test", "--no-warnings", "--enable-source-maps", "--experimental-strip-types", "--experimental-transform-types", "--abort-on-uncaught-exception", "--check", "--interactive", "-c", "-i"},
    "python": {"-" + character for character in "bBdEiIOPqRsSuvx"},
    "python3": {"-" + character for character in "bBdEiIOPqRsSuvx"},
    "bash": {"-" + character for character in "abefhkmnptuvxBCEHPTlirs"} | {"+" + character for character in "abefhkmnptuvxBCEHPTlirs"} | {"--debugger", "--dump-po-strings", "--dump-strings", "--noprofile", "--norc", "--posix", "--restricted", "--verbose", "--login"},
    "sh": {"-" + character for character in "aefnuvxCImps"} | {"+" + character for character in "aefnuvxCImps"},
}

VALUE_OPTIONS = {
    "python": {"-W", "-X", "--check-hash-based-pycs"},
    "python3": {"-W", "-X", "--check-hash-based-pycs"},
    "bash": {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"},
    "sh": {"-o", "+o"},
    "node": {
        "--allow-fs-read", "--allow-fs-write", "--build-snapshot-config", "--conditions",
        "--cpu-prof-dir", "--cpu-prof-interval", "--cpu-prof-name", "--debug-port",
        "--diagnostic-dir", "--disable-proto", "--disable-warning", "--dns-result-order",
        "--env-file", "--env-file-if-exists", "--experimental-config-file",
        "--experimental-default-type", "--experimental-loader", "--experimental-sea-config",
        "--experimental-package-map", "--experimental-test-tag-filter", "--experimental-test-isolation", "--heap-prof-dir", "--heap-prof-interval",
        "--heap-prof-name", "--heapsnapshot-near-heap-limit", "--heapsnapshot-signal",
        "--icu-data-dir", "--import", "--input-type", "--inspect-port",
        "--inspect-publish-uid", "--loader", "--localstorage-file", "--max-http-header-size",
        "--max-old-space-size", "--max-old-space-size-percentage", "--max-semi-space-size",
        "--network-family-autoselection-attempt-timeout", "--openssl-config",
        "--redirect-warnings", "--report-dir", "--report-directory", "--report-filename",
        "--report-signal", "--require", "--secure-heap", "--secure-heap-min",
        "--snapshot-blob", "--stack-trace-limit", "--test-concurrency",
        "--test-coverage-branches", "--test-coverage-exclude", "--test-coverage-functions",
        "--test-coverage-include", "--test-coverage-lines", "--test-name-pattern",
        "--test-global-setup", "--test-isolation", "--test-random-seed", "--test-rerun-failures",
        "--test-reporter", "--test-reporter-destination", "--test-shard",
        "--test-skip-pattern", "--test-timeout", "--title", "--tls-cipher-list",
        "--tls-keylog", "--trace-event-categories", "--trace-event-file-pattern",
        "--trace-require-module", "--unhandled-rejections", "--use-largepages",
        "--v8-pool-size", "--watch-kill-signal", "--watch-path", "-C", "-r",
    },
}


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


def _shell_segments(command, separators=";&|\n"):
    """Split direct shell commands while retaining quoted/escaped separators."""
    start, quote, escaped, comment = 0, None, False, False
    for index, character in enumerate(command):
        if comment:
            if character == "\n":
                comment = False
                start = index + 1
            continue
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif quote:
            if character == quote:
                quote = None
        elif character in {"'", '"'}:
            quote = character
        elif character == "#" and (index == 0 or command[index - 1] in " \t\r\n;&|()"):
            yield command[start:index]
            comment = True
        elif character in separators:
            yield command[start:index]
            start = index + 1
    if not comment:
        yield command[start:]


def _shell_context_gap(segment, *, context_only=False):
    """Identify unsupported syntax, separating word expansion from shell structure."""
    quote, escaped, word_start = None, False, 0
    for index, character in enumerate(segment):
        if escaped:
            if character == "\n":
                return "shell line continuation is outside literal-path audit scope"
            escaped = False
            continue
        if quote is None and character.isspace():
            word_start = index + 1
            continue
        if character == "\\" and quote != "'":
            escaped = True
        elif quote == "'":
            if character == "'":
                quote = None
        elif quote is None and (character in "`{}()<>" or segment[index:index + 2] == "$("):
            return "shell control syntax is outside literal-path audit scope"
        elif not context_only and (character in "$`" or (quote is None and
                (character in "*?[]" or (character == "~" and (index == word_start or
                 (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=", segment[word_start:index])
                  or (segment[index - 1] == ":" and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", segment[word_start:index])))))))):
            return "shell word expansion is outside literal-path audit scope"
        elif quote:
            if character == quote:
                quote = None
        elif character in {"'", '"'}:
            quote = character
    return None


def _fixed_word_arity(raw):
    """Bounded proof that a supported option value remains one shell argument."""
    quote, escaped = None, False
    for index, character in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote != "'":
            escaped = True
        elif quote == "'":
            if character == "'":
                quote = None
        elif quote == '"':
            if character == '"':
                quote = None
            elif character == "$":
                # Ordinary quoted scalar expansions have fixed arity. Positional
                # arrays and complex parameter/substitution forms stay unresolved.
                tail = raw[index:]
                if not re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9*#?$!]|\{[A-Za-z_][A-Za-z0-9_]*\})", tail):
                    return False
            elif character == "`":
                return False
        elif character in {"'", '"'}:
            quote = character
        elif character in "$`*?[]{}()<>" or character.isspace():
            return False
    return quote is None and not escaped


def _attached_option_value(token, interpreter):
    if token.startswith("--"):
        return "=" in token and token.split("=", 1)[0] in VALUE_OPTIONS[interpreter]
    if not token.startswith(("-", "+")):
        return False
    for position, character in enumerate(token[1:], start=1):
        option = token[0] + character
        if option in VALUE_OPTIONS[interpreter]:
            return position < len(token) - 1
        if option not in BOOLEAN_OPTIONS[interpreter]:
            return False
    return False


def _entrypoint_target(token, entry_url, unresolved=None):
    try:
        target = token
        if entry_url:
            parsed = urlsplit(token)
            if parsed.scheme == "file" and parsed.netloc not in {"", "localhost"}:
                raise ValueError("unsupported file URL authority")
            if parsed.scheme not in {"", "file"}:
                return None
            if re.search(r"%(?![0-9a-fA-F]{2})|%(?:2[fF]|5[cC])", parsed.path):
                raise ValueError("invalid or unsupported encoded URL path separator")
            target = unquote(parsed.path, errors="strict")
        if not target or "\0" in target:
            raise ValueError("empty or NUL-containing path")
        return target
    except (ValueError, UnicodeError) as error:
        if unresolved is not None:
            unresolved.append(f"unresolved entrypoint {token!r}: {error}")
    return None


def _local_script_targets(command, unresolved=None):
    """Yield direct file operands after documented interpreter options.

    This is a static audit of direct invocations, not a shell evaluator.
    Python -W/-X, Bash -o/-O and startup files, and common Node value options
    consume their arguments; attached values and -- delimiters are supported.
    """
    cwd_unknown = False
    for segment in _shell_segments(command):
        if not segment.strip():
            continue
        gap = _shell_context_gap(segment)
        if gap and unresolved is not None:
            unresolved.append(gap)
        prior_cwd_unknown = cwd_unknown
        cwd_unknown = cwd_unknown or bool(_shell_context_gap(segment, context_only=True))
        try:
            tokens = shlex.split(segment)
        except ValueError as error:
            cwd_unknown = True
            if unresolved is not None:
                unresolved.append(f"unparseable package script: {error}")
            continue
        raw_words = [word for word in _shell_segments(segment, " \t\r") if word]
        while tokens and raw_words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", raw_words[0]):
            tokens.pop(0)
            raw_words.pop(0)
        if not tokens:
            continue
        if _shell_context_gap(raw_words[0]):
            cwd_unknown = True  # A dynamic command could resolve to a shell builtin.
            continue
        interpreter = Path(tokens[0]).name
        if interpreter in {"cd", "pushd", "popd"}:
            cwd_unknown = True
            if unresolved is not None:
                unresolved.append("working-directory change is outside direct-script audit scope")
            continue
        if interpreter not in LOCAL_SCRIPT_INTERPRETERS:
            cwd_unknown = True
            if unresolved is not None:
                unresolved.append(f"command is outside direct interpreter audit scope: {tokens[0]!r}")
            continue
        if prior_cwd_unknown:
            if unresolved is not None:
                unresolved.append(f"script target after working-directory change is unresolved: {segment.strip()!r}")
            continue
        non_file_modes = NON_FILE_MODES[interpreter]
        entry_url = False
        inspecting = False
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if _shell_context_gap(raw_words[index]):
                if not _attached_option_value(token, interpreter) or not _fixed_word_arity(raw_words[index]):
                    break
            if interpreter == "node" and token == "inspect" and not inspecting:
                inspecting = True
                index += 1
                continue
            if inspecting and re.fullmatch(r"[^:]+:\d+", token):
                break  # Remote debugger attachment.
            if interpreter == "node" and token in {"--entry-url", "--experimental-entry-url"}:
                entry_url = True
                index += 1
                continue
            if token == "--":
                if (index + 1 < len(tokens) and tokens[index + 1] != "-"
                        and not _shell_context_gap(raw_words[index + 1])):
                    target = _entrypoint_target(tokens[index + 1], entry_url, unresolved)
                    if target is not None:
                        yield target
                break
            if token == "-" or token.split("=", 1)[0] in non_file_modes:
                break
            if token in VALUE_OPTIONS[interpreter]:
                if index + 1 < len(raw_words) and not _fixed_word_arity(raw_words[index + 1]):
                    break
                index += 2
                continue
            if token.startswith("-") or (interpreter in {"bash", "sh"} and token.startswith("+")):
                if token.startswith("--"):
                    option = token.split("=", 1)[0]
                    if option not in BOOLEAN_OPTIONS[interpreter] and option not in VALUE_OPTIONS[interpreter] and not (inspecting and re.fullmatch(r"--port=\d+", token)):
                        if unresolved is not None:
                            unresolved.append(f"interpreter option arity is unresolved: {token!r}")
                        break
                # Short options may be clustered or carry an attached argument.
                non_file = False
                if not token.startswith("--"):
                    modes = {mode[1:] for mode in non_file_modes if len(mode) == 2}
                    if interpreter in {"bash", "sh"}:
                        modes.add("s")  # Read commands from stdin.
                    for position, option in enumerate(token[1:], start=1):
                        if (token[0] == "-" and option in modes) or (interpreter == "bash" and option == "s"):
                            non_file = True
                            break
                        if token[0] + option in VALUE_OPTIONS[interpreter]:
                            if position == len(token) - 1:
                                if index + 1 < len(raw_words) and not _fixed_word_arity(raw_words[index + 1]):
                                    non_file = True
                                index += 1
                            break
                        if token[0] + option not in BOOLEAN_OPTIONS[interpreter]:
                            if unresolved is not None:
                                unresolved.append(f"interpreter option arity is unresolved: {token!r}")
                            non_file = True
                            break
                if non_file:
                    break
                index += 1
                continue
            target = _entrypoint_target(token, entry_url, unresolved)
            if target is not None:
                yield target
            break


def _check_package_scripts(target, sink, unresolved):
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
        script_unresolved = []
        for raw_path in _local_script_targets(command, script_unresolved):
            try:
                candidate = Path(raw_path)
                local = candidate.resolve() if candidate.is_absolute() else (target / candidate).resolve()
            except (ValueError, OSError) as error:
                script_unresolved.append(f"unresolved local path {raw_path!r}: {error}")
                continue
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
        unresolved.extend(f"package script {name}: {item}" for item in script_unresolved)


def _read_source_pin():
    """Read the canonical identity shipped with both source and wheel installs."""
    data = json.loads(files("pubskill_lib").joinpath("_source.json").read_text(encoding="utf-8"))
    return data["commit"]


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
            _check_package_scripts(target, sink, document["hmmm"])

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
