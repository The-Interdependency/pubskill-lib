name: pubskill-lib
description: |
  Public distribution repo for The-Interdependency/skill-lib.
  Human entry: README.md. Population procedure: HANDOFF.md.
  If you are an agent in this repo, read this file, then HANDOFF.md, then SOURCE.md.

# You are an agent in The-Interdependency/pubskill-lib

This repository is not the skill catalog. The catalog is skill-lib.

## Binding rules

1. Do not invent a second msdmd, a second findings schema, or a second audit doctrine.
2. Do not copy org-only skills into this tree (canon, the-interdependency, meta, loop-eng, ucns-option-selection, visitor-intro, and anything marked org-only).
3. Do not put cosmology on the first screen of README.md.
4. Do not stamp `verified` unless a gate was actually re-run.
5. Unresolved work stays `hmmm`. Do not write success prose over missing runners.
6. Vendored skills must cite the skill-lib SHA in SOURCE.md and in `.agents/skills/README.md`.
7. If skill-lib and this repo disagree, skill-lib wins for skill text; this repo wins for CLI entrypoint, fixtures, and public README.

## Load order

1. README.md — public claims
2. HANDOFF.md — work remaining
3. SOURCE.md — pin
4. Any local `SKILL.md` under `.agents/skills/` after it exists

## Definition of a finished first tag

`v0.2.0` is allowed only when the commands in README.md run on a clean clone and write findings for `examples/neglected-repo`.
