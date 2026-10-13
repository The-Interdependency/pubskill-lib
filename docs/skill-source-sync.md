# Updating the canonical public skill catalog

`skill-lib` owns skill text, MSDMD readers and their contracts. `pubskill-lib`
owns its public CLI, fixtures, packaging and hosted integration. Propagation
transfers source bytes, not implementation authority or behavioral verification.

The propagated catalog is every skill listed in the pinned producer
`skills.json` (currently 44 skills), plus their referenced shared doctrine and
the producer index itself. The packaged `_msdmd_universal.py` must match the
vendored canonical parser byte for byte. Do not reinterpret schema-1 findings
as native schema-2 collections.

## Reproduce propagation

Resolve and validate an exact merged skill-lib commit first. With clean adjacent
checkouts, use that immutable commit instead of an unpinned branch. This example
replays the current publication pin; select a newly verified SHA for a later update:

```bash
PIN=$(python -c 'import json; print(json.load(open("src/pubskill_lib/_source.json"))["commit"])')
git -C ../skill-lib checkout --detach "$PIN"
python ../skill-lib/tools/propagate_skills.py . --apply
git -C ../skill-lib show "$PIN:skills.json" > .agents/skills/skills.json
cp ../skill-lib/msdmd/parsers/universal.py src/pubskill_lib/_msdmd_universal.py
python tools/build_catalog.py
```

The propagation tool's default selection copies all skills in `skills.json`;
do not filter to a subset by hand. In the same commit, update `SOURCE.md`
(SHA and source commit date when they change, and the catalog description),
`src/pubskill_lib/_source.json`, `examples/neglected-repo/expected-findings.json`
(source_pin only; preserve the fixture's expected defects), and the source
participant in `docs/work-graphs/skill-source-sync.json`. Update the explicit
canonical checkout revision in `.github/workflows/skill-source.yml` as well:
this is a separately reviewed trust anchor, not a PR-supplied checkout parameter.
The propagation tool updates `.agents/skills/README.md`; `tools/build_catalog.py`
regenerates `.agents/skills/catalog.json`. Recompute the graph digest over
exactly `repositories` and `boundaries`, using sorted JSON keys and compact
separators. Keep participant order stable. The PubSkill participant identifies the
pre-update consumer source, not a self-referential final commit.

## Verification

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/findings.json
python tools/build_catalog.py --out /tmp/catalog.json
cmp /tmp/catalog.json .agents/skills/catalog.json
```

The `canonical-source` CI job checks out its explicit trusted producer pin,
rejects publication metadata that differs, compares every complete skill tree,
the producer `skills.json`, shared doctrine and the packaged parser, and replays
the catalog manifest byte for byte. It does not rewrite source before checking
it. Existing CI separately exercises Python 3.11/3.12, clean-wheel behavior,
reproducible release archives and source-distribution replay. New regression
tests exercise the actual vendored Python native reader, prove that inspected
code is not executed, and require stale projections to fail verification.
Catalog tests reject removed or added producer skills, mutated vendored bytes,
duplicate names and non-replayable manifests.

The schema-2 collector and optional parser-runtime declarations travel with the
source distribution. Installing the public wheel does not expose a new hosted
collection API; the wheel's existing inspector and Examiner interfaces remain the
public contract. Native reader dependencies remain declared in
`.agents/skills/msdmd/requirements.txt` and `package-lock.json`; missing optional
runtimes must remain visible as unsupported coverage.

## Rollback and hmmm

Revert the propagation change as one unit to restore skill bytes and every pin.
Do not republish the immutable `v0.2.0` tag. A source update is not a release or a
cloud deployment. Hosted collection/query/check integration and the Amazon MCP
adapter remain separate work.
