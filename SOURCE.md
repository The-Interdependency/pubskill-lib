# Source pin

Canon: https://github.com/The-Interdependency/skill-lib

| Field | Value |
|---|---|
| Pinned SHA | `3001c1a70c1c9d5a063325193ed4ee6db73cd765` |
| Pinned date | 2026-11-15 |
| Pin meaning | exact canonical source used for the vendored public skill slice |
| Runnable subset | `msdmd` (runnable), `repo-audit-repair` (contract), `manifest`, `llms-build` |

`manifest` and `llms-build` ship stdlib runners. `skills.json` at this pin marks only `msdmd` as `runnable` and `repo-audit-repair` as `contract`; it does not assign a status field to the other two.

The `llms-build` runner is vendored at repo-root `llms/__init__.py` and `llms/build.py` so `python -m llms.build` works. skill-lib's own `llms/metadata.py` is not copied; that file is the producer's publication source, not part of the portable runner.

## Declared derived copies

`char-compress` is a public core of skill-lib's `char-compress`, not an exact copy.
By owner ruling, the public copy omits org placement, the org-project relation
sections, and the optional local text-stack notation, and its fixture examples
use neutral names. The checker `char_compress_check.py` is byte-identical.
`docs/derived-copies.json` records the source path, source SHA-256 and consumer
SHA-256 of every file, plus the removed and replaced sections. The
`canonical-source` CI job fails if a recorded source hash differs from the
trusted producer checkout, if published bytes differ from the record, or if the
skill directory holds an unrecorded file. A pin move that changes any recorded
source file needs a fresh redaction review and both hashes updated.

Update this file in the same commit that propagates vendored skills.

Do not vendor from unpinned `main`.
