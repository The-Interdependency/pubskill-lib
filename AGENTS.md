name: pubskill-lib
description: |
  Public distribution repo for The-Interdependency/skill-lib.
  Human entry: README.md. VM entry: HANDOFF.vm.md. Population: HANDOFF.md.
  If you are an agent in this repo, read this file, then the matching handoff.

# You are an agent in The-Interdependency/pubskill-lib

This repository is not the skill catalog. The catalog is skill-lib.

## Load order

If host is a VM:

1. HANDOFF.vm.md
2. this file
3. HANDOFF.md
4. SOURCE.md

Otherwise:

1. README.md
2. HANDOFF.md
3. SOURCE.md
4. Any local SKILL.md under `.agents/skills/` after it exists

## Binding rules

1. Do not invent a second msdmd, a second findings schema, or a second audit doctrine.
2. Populate `.agents/skills/` only by canonical propagation: run `skill-lib/tools/propagate_skills.py` from the exact pinned producer commit with its default all-skills selection, then copy the pinned producer `skills.json`. Do not hand-copy, filter, or independently rewrite canonical skill files. Org-only skills travel as source-pinned bytes and remain procedural guidance; do not promote them into public org doctrine claims.
3. Do not put cosmology on the first screen of README.md.
4. Do not stamp `verified` unless a gate was actually re-run.
5. Unresolved work stays `hmmm`. Do not write success prose over missing runners.
6. Vendored skills must cite the skill-lib SHA in SOURCE.md and in `.agents/skills/README.md`.
7. If skill-lib and this repo disagree, skill-lib wins for skill text; this repo wins for CLI entrypoint, fixtures, and public README.
8. In a VM: no push, no tag, no skill-lib writes, no target-repo installs, unless the env vars in HANDOFF.vm.md are set.

The full-catalog parity work order (branch `a0(aamcp)`,
`DEEPSEEK-PUBSKILL-PARITY-MCP-HANDOFF.md`) supersedes the earlier two-skill
public-slice scope in `HANDOFF.md`; where they conflict, the work order wins.

## Definition of a finished first tag

`v0.2.0` is allowed only when the commands in README.md run on a clean clone and write findings for `examples/neglected-repo`. A VM receipt is not a tag.
