# HANDOFF.vm — machine contract

Execute `HANDOFF.md` inside an isolated VM. This file is the VM wrapper. Load it first.

## Identity

```
role: populate-agent
repo: The-Interdependency/pubskill-lib
canon: The-Interdependency/skill-lib
work_product: v0.2.0 inspect CLI + fixture findings
host: ephemeral VM
```

## Workspace

```
$WORK          default /work
$PUB           $WORK/pubskill-lib
$CANON         $WORK/skill-lib
$ARTIFACTS     $WORK/artifacts
```

Create all three. Do not write outside `$WORK`.

## Allowed inputs

- git clone of the two remotes above (HTTPS)
- Python 3.11+ from the image
- stdlib + pip install of *this* package only (`pip install -e $PUB`)
- `SOURCE.md` pin SHA for skill-lib

## Forbidden unless explicitly exported

| Action | Default | Enable |
|---|---|---|
| `pip install` of target-repo deps | no | never for v0.2 |
| run target test suite / `--run` | no | `ALLOW_RUN=1` (not this handoff) |
| `git push` / `gh` write | no | `PUSH=1` and credentials |
| create git tags | no | `PUSH=1` |
| edit skill-lib (status field, ORG_DISTRIBUTION) | no | `WRITE_CANON=1` |
| network except git clone of the two remotes | no | needed for pip only if index required |
| secrets harvest, SSH keys, cloud metadata | no | never |

If `WRITE_CANON` is unset, skip HANDOFF prerequisite edits to skill-lib. Implement the inspect CLI in pubskill-lib using repo-audit-repair *classes only*. Record the skipped prerequisite as `hmmm` in `$ARTIFACTS/receipt.md`.

If `PUSH` is unset, leave commits in the local `$PUB` clone. Receipt must say `push: not performed`.

## Boot sequence

```bash
set -euo pipefail
mkdir -p "$WORK" "$ARTIFACTS"
cd "$WORK"
git clone https://github.com/The-Interdependency/pubskill-lib "$PUB"
PIN=$(sed -n 's/.*`\([0-9a-f]\{40\}\)`.*/\1/p' "$PUB/SOURCE.md" | head -1)
git clone https://github.com/The-Interdependency/skill-lib "$CANON"
git -C "$CANON" checkout "$PIN"
```

Then execute HANDOFF.md steps A–F inside `$PUB`.
Do not start at G.

## Resource invariant

Inspect is I/O on files. Do not compile the target, install its deps, pull containers, or start browsers. A placeholder CI `echo` is evidence, not a job to run.

If disk, CPU, or network is scarce, finish schema + fixture + inspect before vendoring skills. Vendoring is optional for the first passing receipt.

## Receipt (required)

Write `$ARTIFACTS/receipt.md`:

```
clone_pub: <sha>
clone_canon: <sha> (pin match: yes|no)
steps_done: A,B,C,...
steps_skipped: ...
push: not performed | <url>
verified_stamp_used: no
commands:
  python -m pubskill_lib.audit examples/neglected-repo --out artifacts/findings.json
result: pass | fail
hmmm: <unresolved>
```

Copy `findings.json` to `$ARTIFACTS/findings.json` when the CLI exists.

## Exit

- 0: A–D pass locally (install, import, fixture audit writes JSON)
- 2: environment cannot clone or no Python 3.11+
- 3: tool/schema failure
- 4: fixture compare failure

Do not exit nonzero because neglected-repo is sick. That is the point of the fixture.

## Prompt to paste into the VM agent

```
Read /work/pubskill-lib/AGENTS.md, then /work/pubskill-lib/HANDOFF.vm.md,
then /work/pubskill-lib/HANDOFF.md. Execute A-F in the VM contract.
Do not push. Do not tag. Do not write skill-lib unless WRITE_CANON=1.
Stop when examples/neglected-repo yields findings.json from the CLI.
Leave a receipt in /work/artifacts/receipt.md.
```
