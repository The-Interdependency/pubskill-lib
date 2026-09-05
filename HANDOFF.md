# HANDOFF — populate pubskill-lib with clone utility

This file is the work order. Execute in order. Do not skip to features.

Owner repo: `The-Interdependency/pubskill-lib`  
Canon: `The-Interdependency/skill-lib`  
Current pin: see `SOURCE.md`  
Public claims: `README.md`  
Agent contract: `AGENTS.md`

## Goal

A stranger clones this repository, runs the commands in README.md, and gets a findings file for `examples/neglected-repo`.

That is `v0.2.0`. Nothing else is the first tag.

## Non-goals for this handoff

- Do not port the full skill-lib catalog.
- Do not implement `--fix-one` until inspect works (that is `v0.3.0`).
- Do not host a SaaS.
- Do not rewrite msdmd.
- Do not add Way / UCNS / energy text to README.

## Prerequisite in skill-lib (do this first if missing)

1. Add `status` (`runnable` | `contract` | `org-only`) and optional `runner` to `skills.json`.
2. Mark only skills that execute in-repo as `runnable`.
3. Confirm `python -m unittest discover -s tests` passes on a clean skill-lib clone.
4. If that clone path fails, fix skill-lib before writing code here.

If `repo-audit-repair` is still contract-only, the public CLI may live in *this* repo as a thin inspector that follows that skill's classification rules. Do not invent a sixth findings class.

Allowed classes: `defect`, `environment`, `external`, `policy`, `hmmm`.

## Target tree

```
pubskill-lib/
  README.md                 # already present; update commands only when they work
  AGENTS.md                 # already present
  SOURCE.md                 # already present; update SHA when vendoring
  HANDOFF.md                # this file
  LICENSE                   # MPL-2.0
  pyproject.toml            # package pubskill_lib
  src/pubskill_lib/
    __init__.py
    audit.py                # CLI: inspect a repo path, write findings.json
    schema.py               # findings schema
  tests/
    test_audit_fixture.py
    test_schema.py
  examples/neglected-repo/
    README.md               # lies: missing file, dead link
    pyproject.toml          # or package.json; one stale-looking dep name is enough
    .github/workflows/ci.yml  # claims tests; runs echo ok
    tests/test_dummy.py     # real test that would fail if --run is used later
    expected-findings.json
  .agents/skills/README.md  # cites skill-lib SHA
  .agents/skills/<slice>/   # only runnable slice, propagated, not rewritten
  .github/workflows/ci.yml  # unittest + audit fixture compare
```

## Step A — package skeleton

Create `pyproject.toml` so `pip install -e .` works on Python 3.11+ with no extra native deps.

Package name: `pubskill-lib`  
Import name: `pubskill_lib`  
Console optional: `pubskill-audit`

Acceptance:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
python -c "import pubskill_lib"
```

## Step B — findings schema

`findings.json` shape:

```json
{
  "schema_version": 1,
  "tool": "pubskill-lib",
  "source_pin": "<skill-lib SHA or hmmm>",
  "target": {
    "path": "",
    "commit": "hmmm",
    "remote": "hmmm",
    "dirty": false
  },
  "surfaces": [],
  "findings": [
    {
      "id": "F001",
      "surface": "docs|ci|deps|identity|tests",
      "claim": "",
      "evidence": "",
      "class": "defect",
      "owner": "repository|environment|external|policy|hmmm",
      "verified": false
    }
  ],
  "hmmm": []
}
```

`verified` defaults false. Absence of a finding is not health.

## Step C — inspect CLI (no execute by default)

```bash
python -m pubskill_lib.audit PATH --out findings.json
```

v0.2 inspect only:

- read README / pyproject / package.json / lockfiles / `.github/workflows/*`
- record identity if `.git` exists, else `hmmm`
- flag README links to missing local files
- flag workflows that claim tests but only `echo`
- flag missing advertised scripts
- do not install target deps
- do not run target tests unless `--run` (defer `--run` if timeboxed; leave it `hmmm` in CLI help)

Exit 0 if the tool ran. Do not exit nonzero just because the target repo is sick. Exit nonzero for tool/schema failures.

## Step D — fixture

`examples/neglected-repo` must contain at least three evidenced defects the CLI will see without `--run`:

1. README references a file that does not exist
2. CI workflow named like tests that does not invoke a test runner
3. a declared script or extra path that is missing

Commit `examples/neglected-repo/expected-findings.json` produced by the CLI, then locked.

Acceptance:

```bash
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/out.json
python -m tests.compare_findings /tmp/out.json examples/neglected-repo/expected-findings.json
```

Compare on `id`, `class`, and `surface`. Allow free text drift in `evidence` only if you explicitly snapshot it.

## Step E — vendor the slice

From a checkout of skill-lib at the SOURCE.md SHA:

```bash
python tools/propagate_skills.py ../pubskill-lib \
  --skills msdmd repo-audit-repair \
  --apply
```

Add other skills only if the CLI imports them. Update SOURCE.md in the same commit.

If propagate needs a skills filter that does not exist, copy the two skill directories by hand and write `.agents/skills/README.md` with the SHA. Do not copy the rest of skill-lib.

## Step F — CI in this repo

On push/PR to `main`:

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/out.json
```

Fail the job if schema or fixture compare fails. Do not fail because neglected-repo has findings.

## Step G — close the public door

Only when A–F pass on a clean clone:

1. Rewrite README status table: inspect ships; `--fix-one` still not shipped.
2. Tag `v0.2.0`.
3. Add `The-Interdependency/pubskill-lib` to skill-lib `ORG_DISTRIBUTION.md` consumer list / drift matrix.
4. Leave `--fix-one` as a new handoff section, not part of v0.2.0.

## v0.3.0 (later, not this handoff)

`--fix-one` allowed fixes:

- remove or correct a README local path that 404s
- point placeholder CI at the real test command if that file exists

Re-run inspect. Stamp `verified` on that one finding only.

## Done / not done

Done: clean clone → install → unittest → audit fixture → findings.json.

Not done: stars, SaaS, full catalog, architectural-drift theater, selling VERIFIED on the zip.

hmmm — if the fixture expected file was authored by hand and never produced by the CLI, the utility is still fake.
