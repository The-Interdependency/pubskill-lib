# pubskill-lib

Public distribution of [skill-lib](https://github.com/The-Interdependency/skill-lib).

Clone this repo when you want a command that inspects a local repository and writes findings. The full catalog, org doctrine, and unfinished skills stay in skill-lib. This repo is the subset a stranger can run.

## Status

The inspect CLI implementation passes the repository gate; the `v0.2.0` release tag is not published yet.

| Claim | State |
|---|---|
| Canon | `The-Interdependency/skill-lib` |
| This repo | distribution + public CLI + fixtures |
| Clone / run / findings | **implementation ready** — release pending |
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

Those commands are the definition of done for the first utility tag (`v0.2.0`). They run in GitHub CI from a clean checkout; publish the tag only after the release gate is explicitly completed.

## Inspect CLI

`v0.2` inspects one **local repository path** without executing the target repository:

```bash
python -m pubskill_lib.audit PATH --out findings.json
```

It writes:

- identity when the target contains `.git` (remote, commit, dirty state)
- README links to missing local files or paths that escape the repository
- obvious test-workflow no-ops
- Python `pyproject.toml` console scripts whose modules are missing
- direct local `package.json` script targets whose referenced files are missing or escape the repository
- findings classified as `defect`, `environment`, `external`, `policy`, or `hmmm`

The inspector does **not** yet clone URLs, select remote commits, execute target tests, or repair the target. Those are later capabilities and must not be inferred from the schema.

## Repository examiner (BYOK)

A separate documentation examiner builds on the repository evidence substrate:

```bash
python -m pubskill_lib.examine --repo /path/to/repo --json
python -m pubskill_lib.examine --repo /path/to/repo --apply --narrate
```

With `--apply`, the examiner inventories actual code, writes descriptive `NARRATIVE` msdmd blocks into supported source files, maintains source-boundary RATIOS placement, and assembles `docs/examiner/EXAMINER.md`. Narratives are evidence-bound to the source hash that produced them; changed source without a re-narrate is marked stale. The tool never writes outside the repository boundary it was pointed at.

BYOK credentials may come from the process environment or a `.env` file. `.env` files are ignored by this repository. To prevent a target repository from redirecting an operator credential, provider base-URL overrides are accepted only from the process environment, not from `.env`:

```text
OPENAI_API_KEY / OPENAI_MODEL
ANTHROPIC_API_KEY / ANTHROPIC_MODEL
OPENAI_BASE_URL / ANTHROPIC_BASE_URL   # process environment only
```

Multiple configured providers are attempted sequentially as fallback. Unsupported or not-faithfully-computable metrics remain `hmmm`; they are not guessed.

## License

MPL-2.0, same as skill-lib. Changes to MPL-covered files must be published.

## Canon

Do not add skills here first. Add them in skill-lib, mark them appropriately, pin the SHA in `SOURCE.md`, then propagate the public slice.
