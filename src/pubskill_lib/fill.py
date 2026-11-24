"""Fail-closed fill-in generator for org skill templates.

Usage:
    python -m pubskill_lib.fill NAME|all --config FILE --out DIR [--check] [--force]
    python -m pubskill_lib.fill --verify

A template lives at ``templates/<name>/`` and is never an installed skill.
The only way to make a usable copy is this command, which writes
``<out>/<name>/`` from the template plus a consumer config file.

Fail closed: a missing, empty, or malformed field, an unknown placeholder,
or an unused config key exits non-zero and writes nothing. Config values are
never printed; diagnostics name fields and paths only. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

try:  # Python 3.11+ stdlib
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - requires-python is >=3.11
    tomllib = None

TEMPLATE_SCHEMA = "pubskill-lib.template"
LOCK_SCHEMA = "pubskill-lib.templates-lock"
LOCK_FILE = "TEMPLATES.lock.json"
DENYLIST_FILE = "leak-denylist.json"
TEMPLATE_SUFFIX = ".tmpl"
PLACEHOLDER_OPEN = "{{pubskill"
PLACEHOLDER = re.compile(r"\{\{pubskill:([a-z][a-z0-9_]{0,63})\}\}")
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class FillError(Exception):
    """A fail-closed refusal. ``problems`` lists every reason, never a value."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def default_templates_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[2] / "templates"
    return candidate if candidate.is_dir() else None


def _digest(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for rel in sorted(files):
        raw = rel.encode("utf-8")
        h.update(len(raw).to_bytes(8, "big") + raw)
        h.update(len(files[rel]).to_bytes(8, "big") + files[rel])
    return h.hexdigest()


def _read_tree(root: Path) -> dict[str, bytes]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise FillError([f"symlink not allowed: {path.relative_to(root).as_posix()}"])
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def list_templates(root: Path) -> list[str]:
    """Every directory under ``root`` is a candidate template.

    Presence of ``template.json`` is not used as a filter: a directory that
    lacks its schema is still listed so ``load_template`` (and therefore
    ``--verify`` and ``all``) reports it instead of silently skipping it.
    """
    return sorted(p.name for p in root.iterdir() if p.is_dir() or p.is_symlink())


def load_template(root: Path, name: str) -> dict:
    if not NAME.match(name) or name == "all":
        raise FillError([f"invalid template name: {name!r}"])
    tdir = root / name
    if tdir.is_symlink():
        raise FillError([f"{name}: template directory must not be a symlink"])
    if not tdir.is_dir():
        raise FillError([f"unknown template: {name}"])
    if not (tdir / "template.json").is_file():
        raise FillError([f"{name}: missing template.json schema"])
    problems = []
    spec = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    if spec.get("schema") != TEMPLATE_SCHEMA or spec.get("version") != 1:
        problems.append(f"{name}: template.json must declare schema {TEMPLATE_SCHEMA} version 1")
    if spec.get("name") != name:
        problems.append(f"{name}: template.json name must equal directory name")
    fields = spec.get("fields")
    if not isinstance(fields, dict) or not fields:
        problems.append(f"{name}: template.json must declare at least one field")
        fields = {}
    for field, meta in sorted(fields.items()):
        if not FIELD.match(field):
            problems.append(f"{name}: invalid field name {field!r}")
            continue
        if not isinstance(meta, dict) or not isinstance(meta.get("description"), str) or not meta["description"].strip():
            problems.append(f"{name}: field {field} needs a description")
            continue
        if not isinstance(meta.get("required"), bool):
            problems.append(f"{name}: field {field} must set required to true or false")
        elif meta["required"] and "default" in meta:
            problems.append(f"{name}: required field {field} must not declare a default")
        elif not meta["required"]:
            default = meta.get("default")
            if not isinstance(default, str) or not default.strip() or CONTROL.search(default):
                problems.append(f"{name}: optional field {field} must declare a non-empty single-line default")
            elif PLACEHOLDER_OPEN in default:
                problems.append(f"{name}: default for field {field} must not contain placeholder syntax")
    files_dir = tdir / "files"
    sources = {}
    if not files_dir.is_dir():
        problems.append(f"{name}: missing files/ directory")
    else:
        try:
            raw_files = _read_tree(files_dir)
        except FillError as exc:
            raw_files = {}
            problems.extend(f"{name}: {p}" for p in exc.problems)
        if not raw_files:
            problems.append(f"{name}: files/ is empty")
        for rel, data in raw_files.items():
            if not rel.endswith(TEMPLATE_SUFFIX):
                problems.append(f"{name}: template file must end with {TEMPLATE_SUFFIX}: {rel}")
                continue
            try:
                sources[rel] = data.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{name}: template file is not UTF-8 text: {rel}")
    used = set()
    for rel, text in sorted(sources.items()):
        start = 0
        while (index := text.find(PLACEHOLDER_OPEN, start)) != -1:
            match = PLACEHOLDER.match(text, index)
            line = text.count("\n", 0, index) + 1
            if not match:
                problems.append(f"{name}: malformed placeholder at {rel}:{line}")
                start = index + len(PLACEHOLDER_OPEN)
                continue
            field = match.group(1)
            used.add(field)
            if field not in fields:
                problems.append(f"{name}: unknown placeholder {field} at {rel}:{line}")
            start = match.end()
    for field in sorted(set(fields) - used):
        problems.append(f"{name}: declared field {field} is never used by a template file")
    if problems:
        raise FillError(problems)
    return {"name": name, "dir": tdir, "fields": fields, "sources": sources}


def load_config(path: Path) -> dict:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        elif suffix == ".toml":
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        else:
            raise FillError([f"config must be .json or .toml: {path.name}"])
    except (OSError, ValueError) as exc:
        raise FillError([f"cannot read config {path.name}: {type(exc).__name__}"]) from None
    if not isinstance(data, dict):
        raise FillError(["config must be a flat table of field = string"])
    return data


def resolve_values(templates: list[dict], config: dict) -> dict:
    """Return field values or raise listing every problem. Never echoes values."""
    problems = []
    declared = {}
    for template in templates:
        for field, meta in template["fields"].items():
            if field not in declared:
                declared[field] = meta
            elif (meta["required"], meta.get("default")) != (declared[field]["required"], declared[field].get("default")):
                problems.append(
                    f"conflicting declarations for field {field} across templates "
                    f"(required/default differ in {template['name']}); fill them separately"
                )
    if problems:
        raise FillError(problems)
    for key in sorted(config):
        if key not in declared:
            problems.append(f"unused config key: {key}")
    values = {}
    for field, meta in sorted(declared.items()):
        if field not in config:
            if meta["required"]:
                problems.append(f"missing required field: {field} ({meta['description']})")
            else:
                values[field] = meta["default"]
            continue
        value = config[field]
        if not isinstance(value, str):
            problems.append(f"field {field} must be a string")
        elif not value.strip():
            problems.append(f"empty field: {field} ({meta['description']})")
        elif CONTROL.search(value):
            problems.append(f"field {field} must be a single line without control characters")
        elif PLACEHOLDER_OPEN in value:
            problems.append(f"field {field} must not contain placeholder syntax")
        else:
            values[field] = value
    if problems:
        raise FillError(problems)
    return values


def render(template: dict, values: dict) -> dict[str, bytes]:
    out = {}
    for rel, text in template["sources"].items():
        rendered = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
        out[rel[: -len(TEMPLATE_SUFFIX)]] = rendered.encode("utf-8")
    out["FILLED_FROM.json"] = (
        json.dumps(
            {
                "schema": "pubskill-lib.filled",
                "version": 1,
                "template": template["name"],
                "template_sha256": template_sha256(template["dir"]),
                "note": "Generated by python -m pubskill_lib.fill. Regenerate instead of editing.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    return out


def template_sha256(tdir: Path) -> str:
    return _digest(_read_tree(tdir))


def _existing(target: Path) -> dict[str, bytes] | None:
    if target.parent.is_symlink() or (target.parent.exists() and not target.parent.is_dir()):
        raise FillError([f"output directory must be a real directory: {target.parent}"])
    if target.parent.exists() and target.resolve().parent != target.parent.resolve():
        raise FillError([f"output path escapes the output directory: {target}"])
    if target.is_symlink():
        raise FillError([f"refusing symlinked output: {target}"])
    if not target.exists():
        return None
    if not target.is_dir():
        raise FillError([f"output path exists and is not a directory: {target}"])
    return _read_tree(target)


def drift(expected: dict[str, bytes], actual: dict[str, bytes] | None) -> list[str]:
    if actual is None:
        return ["(missing output directory)"]
    names = set(expected) | set(actual)
    return sorted(n for n in names if expected.get(n) != actual.get(n))


def write_output(target: Path, files: dict[str, bytes], force: bool) -> str:
    current = _existing(target)
    if current is not None:
        changed = drift(files, current)
        if not changed:
            return "unchanged"
        if not force:
            raise FillError([f"{target} already holds different content ({', '.join(changed)}); pass --force to replace"])
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.fill-", dir=target.parent))
    try:
        for rel, data in files.items():
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        if current is not None:
            retired = Path(tempfile.mkdtemp(prefix=f".{target.name}.old-", dir=target.parent))
            os.rmdir(retired)
            os.rename(target, retired)
            os.rename(staging, target)
            shutil.rmtree(retired)
            return "replaced"
        os.rename(staging, target)
        return "written"
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def load_denylist(root: Path) -> list[tuple[str, re.Pattern]]:
    spec = json.loads((root / DENYLIST_FILE).read_text(encoding="utf-8"))
    rules = []
    for entry in spec["entries"]:
        term = re.escape(entry["term"])
        if entry["match"] == "token":
            pattern = re.compile(rf"(?<![a-z0-9]){term}(?![a-z0-9])", re.IGNORECASE)
        elif entry["match"] == "substring":
            pattern = re.compile(term, re.IGNORECASE)
        else:
            raise FillError([f"denylist entry {entry['term']!r} has unknown match mode"])
        rules.append((entry["term"], pattern))
    return rules


def leak_scan(root: Path, name: str) -> list[str]:
    """Return denylist hits in a template's files, schema, and example config."""
    rules = load_denylist(root)
    hits = []
    for rel, data in sorted(_read_tree(root / name).items()):
        text = data.decode("utf-8", errors="replace")
        for term, pattern in rules:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{name}/{rel}:{line}: org-specific term {term!r}")
    return hits


def verify(root: Path) -> list[str]:
    """CI integrity: schema, lock hashes, example output, leak gate."""
    problems = []
    lock = json.loads((root / LOCK_FILE).read_text(encoding="utf-8"))
    if lock.get("schema") != LOCK_SCHEMA or lock.get("version") != 1:
        problems.append(f"{LOCK_FILE} must declare schema {LOCK_SCHEMA} version 1")
    locked = lock.get("templates", {})
    names = list_templates(root)
    loaded = []
    for name in sorted(set(locked) - set(names)):
        problems.append(f"{LOCK_FILE} lists missing template {name}")
    for name in names:
        try:
            template = load_template(root, name)
        except FillError as exc:
            problems.extend(exc.problems)
            continue
        loaded.append(template)
        problems.extend(leak_scan(root, name))
        if name not in locked:
            problems.append(f"{name}: not recorded in {LOCK_FILE}")
            continue
        actual = template_sha256(template["dir"])
        if locked[name].get("template_sha256") != actual:
            problems.append(f"{name}: template_sha256 drift (computed {actual})")
        example = template["dir"] / "example.config.json"
        if not example.is_file():
            problems.append(f"{name}: missing example.config.json")
            continue
        try:
            output = render(template, resolve_values([template], load_config(example)))
        except FillError as exc:
            problems.extend(f"{name}: example config: {p}" for p in exc.problems)
            continue
        out_hash = _digest(output)
        if locked[name].get("example_output_sha256") != out_hash:
            problems.append(f"{name}: example_output_sha256 drift (computed {out_hash})")
    try:
        resolve_values(loaded, {})
    except FillError as exc:
        problems.extend(p for p in exc.problems if p.startswith("conflicting declarations"))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pubskill_lib.fill", description=__doc__.splitlines()[0])
    parser.add_argument("template", nargs="?", help="template name, or all")
    parser.add_argument("--config", type=Path, help="consumer config (.json or .toml)")
    parser.add_argument("--out", type=Path, help="output directory; writes <out>/<template>/")
    parser.add_argument("--check", action="store_true", help="exit 1 if <out> differs from a fresh fill; write nothing")
    parser.add_argument("--force", action="store_true", help="replace an output directory holding different content")
    parser.add_argument("--templates", type=Path, help="templates directory (default: repository templates/)")
    parser.add_argument("--verify", action="store_true", help="CI gate: schemas, lock hashes, example output, leak gate")
    args = parser.parse_args(argv)
    root = args.templates or default_templates_root()
    if root is None or not root.is_dir():
        print("error: templates directory not found; pass --templates", file=sys.stderr)
        return 2
    try:
        if args.verify:
            if args.template or args.config or args.out or args.check or args.force:
                print("error: --verify takes no other arguments", file=sys.stderr)
                return 2
            problems = verify(root)
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            if problems:
                return 1
            print(f"ok: {len(list_templates(root))} template(s) verified")
            return 0
        if not (args.template and args.config and args.out):
            print("error: NAME|all, --config, and --out are required", file=sys.stderr)
            return 2
        if args.check and args.force:
            print("error: --check and --force are exclusive", file=sys.stderr)
            return 2
        names = list_templates(root) if args.template == "all" else [args.template]
        templates, problems = [], []
        for name in names:
            try:
                templates.append(load_template(root, name))
            except FillError as exc:
                problems.extend(exc.problems)
        if problems:
            raise FillError(problems)
        values = resolve_values(templates, load_config(args.config))
        rendered = {t["name"]: render(t, values) for t in templates}
        # Path-safety preflight for every target before any write, even with --force.
        # --force only waives the content-difference refusal.
        refusals = []
        for name, files in rendered.items():
            try:
                current = _existing(args.out / name)
            except FillError as exc:
                refusals.extend(exc.problems)
                continue
            if not args.check and not args.force and current is not None and drift(files, current):
                refusals.append(f"{args.out / name} already holds different content; pass --force to replace")
        if refusals:
            raise FillError(refusals)
        status = 0
        for name, files in rendered.items():
            target = args.out / name
            if args.check:
                changed = drift(files, _existing(target))
                if changed:
                    status = 1
                    print(f"drift: {target}: {', '.join(changed)}", file=sys.stderr)
                else:
                    print(f"ok: {target}")
            else:
                print(f"{write_output(target, files, args.force)}: {target}")
        return status
    except FillError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
