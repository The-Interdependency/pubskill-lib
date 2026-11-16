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
2. Org-only skills (canon, the-interdependency, meta, loop-eng, ucns-option-selection, visitor-intro, and anything marked org-only) ship only as templates under `templates/<name>/`, never as copies under `.agents/skills/`. Templates are not part of the installed tree. The only way to make a usable copy is `python -m pubskill_lib.fill`, which writes a consumer copy from the template plus the consumer's config file. It exits non-zero and writes nothing when any field is missing, empty, or unknown, and it never writes a guessed value. Every template must pass `python -m pubskill_lib.fill --verify` (schema, lock hashes, example output, leak gate). See `templates/README.md`.
3. Do not put cosmology on the first screen of README.md.
4. Do not stamp `verified` unless a gate was actually re-run.
5. Unresolved work stays `hmmm`. Do not write success prose over missing runners.
6. Vendored skills must cite the skill-lib SHA in SOURCE.md and in `.agents/skills/README.md`.
7. If skill-lib and this repo disagree, skill-lib wins for skill text; this repo wins for CLI entrypoint, fixtures, and public README.
8. In a VM: no push, no tag, no skill-lib writes, no target-repo installs, unless the env vars in HANDOFF.vm.md are set.

## Definition of a finished first tag

`v0.2.0` is allowed only when the commands in README.md run on a clean clone and write findings for `examples/neglected-repo`. A VM receipt is not a tag.
