# HANDOFF — pubskill-lib v0.2 closure

Owner repo: `The-Interdependency/pubskill-lib`  
Canon: `The-Interdependency/skill-lib`  
Current pin: see `SOURCE.md`  
Public claims: `README.md`  
Agent contract: `AGENTS.md`

## Goal

A stranger clones this repository, installs it, runs its tests, audits `examples/neglected-repo`, and gets the expected findings file. That is the `v0.2.0` release gate.

## v0.2 public boundary

The inspect CLI accepts one local repository path:

```bash
python -m pubskill_lib.audit PATH --out findings.json
```

It may inspect README files, `pyproject.toml`, `package.json`, and GitHub workflow text; record local git identity; flag missing local README targets; flag obvious test-workflow no-ops; and flag declared Python or direct local package-script entrypoints that do not exist.

It does not clone remote URLs, select remote commits, install target dependencies, run target tests, repair target repositories, or expose `--fix-one`. Those capabilities require separate versioned work rather than implied v0.2 behavior.

## Source provenance

Vendored public skills must identify the same exact skill-lib SHA in both `SOURCE.md` and `.agents/skills/README.md`. Do not vendor from unpinned `main`.

## Credential boundary

The examiner may read API keys and model names from `.env`, but provider base URL overrides are operator configuration and therefore come only from the process environment. Never allow an inspected repository's `.env` to redirect an ambient operator credential.

## Release gate

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/out.json
```

The first release tag is exactly `v0.2.0`. README may say the implementation is ready on `main` before that tag exists; it must not claim the release exists before the tag is published.

## Generated metadata

`*.egg-info/` is generated build state. It is ignored and must not be tracked. Package/release verification regenerates metadata from `pyproject.toml`.

## hmmm

- Python 3.11 is part of the declared `>=3.11` support range but the current GitHub CI lane is Python 3.12 only. Add a 3.11 CI lane before treating cross-version support as independently witnessed.
- Remote inspection/execution/repair semantics are deliberately outside v0.2; version and specify them before implementation.
