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

Update this file in the same commit that propagates vendored skills.

Do not vendor from unpinned `main`.
