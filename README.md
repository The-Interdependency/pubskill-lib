# pubskill-lib

Public distribution of [skill-lib](https://github.com/The-Interdependency/skill-lib).

Clone this repo when you want a command that inspects a repository and writes findings. The full catalog, org doctrine, and unfinished skills stay in skill-lib. This repo is the subset a stranger can run.

## Status

The inspect CLI ships. Clone, run, get findings.

| Claim | State |
|---|---|
| Canon | `The-Interdependency/skill-lib` |
| This repo | distribution + public CLI + fixtures |
| Clone / run / findings | **shipped** — `v0.2` inspect; see `HANDOFF.md` |
| VM populate | `HANDOFF.vm.md` |
| Source pin | `SOURCE.md` |

If a command is not in this README, it is not a public promise.

## Quickstart

```bash
git clone https://github.com/The-Interdependency/pubskill-lib
cd pubskill-lib
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/findings.json
```

Those commands are the definition of done for the first utility tag (`v0.2.0`). They run on a clean clone.

## What this will do

Inspect one repository path or URL at a named commit and write:

- identity (remote, commit, dirty state, declared instructions)
- claimed gates vs files that exist
- obvious dependency and docs drift
- findings classified as `defect`, `environment`, `external`, `policy`, or `hmmm`

`--run` is opt-in. `verified` is stamped only on a finding whose gate was re-run.

## What this will not do

- audit the whole internet
- execute private CI secrets by default
- rewrite a repo unless `--fix-one` is explicit and bounded
- carry The Interdependent Way, UCNS, or org liturgy on the first screen

## License

MPL-2.0, same as skill-lib. Changes to MPL-covered files must be published.

## Canon

Do not add skills here first. Add them in skill-lib, mark them `runnable`, pin the SHA in `SOURCE.md`, then propagate.
