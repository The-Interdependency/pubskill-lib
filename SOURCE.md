# Source pin

Canon: https://github.com/The-Interdependency/skill-lib

| Field | Value |
|---|---|
| Pinned SHA | `9867ab33877f2b1f50f8a501cf379aa99360bd52` |
| Pinned date | 2026-10-05 |
| Pin meaning | exact canonical source used for the propagated full skill catalog (44 skills) |
| Runnable subset | `msdmd` (runnable), `repo-audit-repair` (contract); all other skills are procedural or metadata guidance |
| Catalog manifest | `.agents/skills/catalog.json`, derived from `.agents/skills/skills.json` and the vendored bytes by `tools/build_catalog.py` |

Update this file in the same commit that propagates vendored skills.

Do not vendor from unpinned `main`.
