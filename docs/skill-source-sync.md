# Updating the canonical public slice

`skill-lib` owns skill text, MSDMD readers and their contracts. `pubskill-lib`
owns its public CLI, fixtures, packaging and hosted integration. Propagation
transfers source bytes, not implementation authority or behavioral verification.

The public slice stays `msdmd` and `repo-audit-repair`, plus their shared doctrine.
The packaged `_msdmd_universal.py` must match the vendored canonical parser byte
for byte. Do not copy organization-only skills or reinterpret schema-1 findings
as native schema-2 collections.

## Reproduce propagation

Resolve and validate an exact merged skill-lib commit first. With clean adjacent
checkouts, use that immutable commit instead of an unpinned branch:

```bash
PIN=<40-character-verified-skill-lib-commit>
git -C ../skill-lib checkout --detach "$PIN"
python ../skill-lib/tools/propagate_skills.py . --skills msdmd repo-audit-repair
python ../skill-lib/tools/propagate_skills.py . --skills msdmd repo-audit-repair --apply
cp ../skill-lib/msdmd/parsers/universal.py src/pubskill_lib/_msdmd_universal.py
```

In the same commit, update `SOURCE.md` (SHA and source commit date),
`src/pubskill_lib/_source.json`, and the source participant in
`docs/work-graphs/skill-source-sync.json`. The propagation tool updates
`.agents/skills/README.md`. Recompute the graph digest over exactly `repositories`
and `boundaries`, using sorted JSON keys and compact separators. Keep participant
order stable. The PubSkill participant identifies the pre-update consumer source,
not a self-referential final commit.

## Verification

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/findings.json
```

The `canonical-source` CI job checks out the exact producer pin and compares both
complete skill trees, shared doctrine and the packaged parser. It does not rewrite
source before checking it. Existing CI separately exercises Python 3.11/3.12,
clean-wheel behavior, reproducible release archives and source-distribution replay.
New regression tests exercise the actual vendored Python native reader, prove that
inspected code is not executed, and require stale projections to fail verification.

The schema-2 collector and optional parser-runtime declarations now travel with
the source distribution. Installing the public wheel does not expose a new hosted
collection API; the wheel's existing inspector and Examiner interfaces remain the
public contract. Native reader dependencies remain declared in
`.agents/skills/msdmd/requirements.txt` and `package-lock.json`; missing optional
runtimes must remain visible as unsupported coverage.

## Rollback and hmmm

Revert the propagation change as one unit to restore skill bytes and every pin.
Do not republish the immutable `v0.2.0` tag. A source update is not a release or a
cloud deployment. Hosted collection/query/check integration and the Amazon MCP
adapter remain separate work.
