# Org skill templates

Org-only skills ship here as templates, never as installed skills. A template
is not usable until `python -m pubskill_lib.fill` writes a consumer copy from it.

No org skills are templated yet. `example-skill/` is synthetic and exists only
for tests and docs. Which org skills get templated is decided in skill-lib
first.

## Layout

```text
templates/
  TEMPLATES.lock.json        template_sha256 and example_output_sha256 per template
  leak-denylist.json         org-specific terms no template may contain
  <name>/
    template.json            field schema
    example.config.json      obviously fake values (ExampleOrg)
    files/**/*.tmpl          template files; output drops the .tmpl suffix
```

Template files end in `.tmpl` so no loader mistakes them for a `SKILL.md`.

## Field schema

`template.json` declares `schema: "pubskill-lib.template"`, `version: 1`,
`name` (the directory name), and `fields`. Each field has a `description` and
`required: true|false`. An optional field must declare a non-empty, single-line
`default` without placeholder syntax. That default is written, reviewed text, not
a guess. A required field has no default. When several templates declare the same
field, their `required` and `default` must agree; `all` and `--verify` reject a
conflict.

## Placeholders

The only placeholder form is `{{pubskill:field_name}}`, where `field_name` is
lowercase `[a-z][a-z0-9_]*`. Any other text starting with `{{pubskill` is a
malformed placeholder and an error. There is no escape syntax, so a template
cannot contain that literal text. The generator also fails on:

- a placeholder whose field is not declared
- a declared field that no template file uses
- a config key that no selected template declares
- a missing or empty required field, or any field that is empty, not a string,
  multi-line, or contains placeholder syntax

All problems are listed together. Messages name fields and paths, never values.

## Generator

```bash
python -m pubskill_lib.fill NAME|all --config FILE --out DIR [--check] [--force] [--templates DIR]
python -m pubskill_lib.fill --verify [--templates DIR]
```

Exit codes: `0` ok, `1` drift (`--check`) or failed `--verify`, `2` refusal or
usage error. Output goes to `DIR/NAME/` along with `FILLED_FROM.json`, which
records the template name and `template_sha256`. Identical existing output is a
no-op. Different existing output is refused unless `--force` is passed. Every
target is checked before anything is written, including under `--force`.
Symlinked or non-directory targets and paths that escape `--out` are always
refused. `--force` only waives the content-difference refusal.

`--templates` defaults to this repository's `templates/` when the package runs
from a source checkout. An installed wheel does not include templates, so pass
`--templates` there.

## CI integrity (`--verify`)

`--verify` runs in CI and in `tests/test_fill.py`. It checks that:

1. every template directory is valid and listed in `TEMPLATES.lock.json`;
   every directory under `templates/` is treated as a template, so one that
   lacks `template.json` (or is a symlink) fails instead of being skipped
2. `template_sha256` matches the template's bytes (template.json, example config, files)
3. rendering `example.config.json` matches `example_output_sha256`
4. the leak gate passes

After an intentional template change, run `--verify` and copy the computed
hashes it prints into the lock file in the same commit.

## Leak gate

`leak-denylist.json` lists org-specific terms. The gate scans every file in a
template directory, including `template.json` and the example config.
Matching is case-insensitive.

- `token`: the term must not be preceded or followed by a letter or digit. This
  is used for short names, so `skill-lib` does not match `pubskill-lib`, and
  `a0` does not match inside a hex digest such as `3a0f`.
- `substring`: the term matches anywhere. This is used only where it is distinctive,
  such as `interdependency`, `hovel`, `ucns`, and `edcm`.

Left out on purpose because they would cause false positives: org repos with common
names (`stack`, `faces`, `.github`) and upstream forks (`openbao`, `infisical`,
`termux-*`). A template can still name those tools generically. hmmm: the list
is a first pass from the org's repository names and known handles. Extend it
when a template is reviewed.
