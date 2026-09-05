# HANDOFF — populate pubskill-lib with clone utility

This file is the work order. Execute in order. Do not skip to features.

If the host is a VM, read `HANDOFF.vm.md` first. VM default: steps A–F only. No push, no tag, no skill-lib writes.

Owner repo: `The-Interdependency/pubskill-lib`  
Canon: `The-Interdependency/skill-lib`  
Current pin: see `SOURCE.md`  
Public claims: `README.md`  
Agent contract: `AGENTS.md`  
VM contract: `HANDOFF.vm.md`

## Goal

A stranger clones this repository, runs the commands in README.md, and gets a findings file for `examples/neglected-repo`.

That is `v0.2.0`. Nothing else is the first tag. A VM receipt is not a tag.

## Non-goals for this handoff

- Do not port the full skill-lib catalog.
- Do not implement `--fix-one` until inspect works (that is `v0.3.0`).
- Do not host a SaaS.
- Do not rewrite msdmd.
- Do not add Way / UCNS / energy text to README.

## Prerequisite in skill-lib

Only if `WRITE_CANON=1`:

1. Add `status` (`runnable` | `contract` | `org-only`) and optional `runner` to `skills.json`.
2. Mark only skills that execute in-repo as `runnable`.
3. Confirm `python -m unittest discover -s tests` passes on a clean skill-lib clone.

VM default: skip this block. Implement the inspect CLI here. Follow repo-audit-repair classes. Do not invent a sixth class.

Allowed classes: `defect`, `environment`, `external`, `policy`, `hmmm`.

## Target tree

```
pubskill-lib/
  README.md
  AGENTS.md
  SOURCE.md
  HANDOFF.md
  HANDOFF.vm.md
  LICENSE
  pyproject.toml
  src/pubskill_lib/
    __init__.py
    audit.py
    schema.py
  tests/
    test_audit_fixture.py
    test_schema.py
  examples/neglected-repo/
    README.md
    pyproject.toml
    .github/workflows/ci.yml
    tests/test_dummy.py
    expected-findings.json
  .agents/skills/README.md
  .agents/skills/<slice>/
  .github/workflows/ci.yml
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
- do not run target tests

Exit 0 if the tool ran. Do not exit nonzero just because the target repo is sick. Exit nonzero for tool/schema failures.

## Step D — fixture

`examples/neglected-repo` must contain at least three evidenced defects the CLI will see without `--run`:

1. README references a file that does not exist
2. CI workflow named like tests that does not invoke a test runner
3. a declared script or extra path that is missing

Write `expected-findings.json` from the CLI output, then lock it.

Acceptance:

```bash
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/out.json
```

Compare on `id`, `class`, and `surface`.

## Step E — vendor the slice

Optional if time or disk is scarce. Prefer A–D first.

From skill-lib at the SOURCE.md SHA, copy only `msdmd` and `repo-audit-repair` into `.agents/skills/` and write `.agents/skills/README.md` with the SHA. Do not copy the rest of skill-lib.

## Step F — tests in this repo

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/out.json
```

A `.github/workflows/ci.yml` may be added. The VM does not push it unless `PUSH=1`.

## Step G — close the public door

Not a VM default. Requires `PUSH=1`.

1. Rewrite README status table: inspect ships.
2. Tag `v0.2.0`.
3. Add this repo to skill-lib consumer list only with `WRITE_CANON=1`.

## Done / not done

Done: clean clone → install → unittest → audit fixture → findings.json.

Not done: stars, SaaS, full catalog, architectural-drift theater, selling VERIFIED on the zip.

hmmm — if the fixture expected file was authored by hand and never produced by the CLI, the utility is still fake.
