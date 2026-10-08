# DeepSeek handoff — pubskill parity, hosted MSDMD, and bounded METAPAT inference

Date: 2026-10-05 (America/Los_Angeles)  
Owner: The Interdependency  
Primary repository: `The-Interdependency/pubskill-lib`  
Canonical producer: `The-Interdependency/skill-lib`

## Read this as the work order

Build `pubskill-lib` into the publicly deployable, MCP-callable runtime of
`skill-lib`. Preserve `skill-lib` as the canonical source. Pubskill must expose
the canonical skill catalog and the real MSDMD collection/query capability; it
must not create a second metadata doctrine, silently flatten schema 2 into the
legacy findings schema, or claim that procedural skill text is executable code.

The earlier `pubskill-lib/HANDOFF.md` deliberately limited the repository to a
two-skill public slice and static inspection. This work order supersedes that
scope restriction. Preserve the verified `v0.2.0` release and its behavior, but
make the new source line a separately versioned parity release.

## Exact starting identities

Work from these identities or explicitly stop if either branch has moved:

| Repository | Required starting identity | Role |
| --- | --- | --- |
| `The-Interdependency/skill-lib` | `9867ab33877f2b1f50f8a501cf379aa99360bd52` | Canonical skill text, MSDMD implementation, readers, schemas and doctrine |
| `The-Interdependency/pubskill-lib` | `bc337e9b6746ad896f527ac867f5458fd9f502aa` | Public package, service, deployment and MCP adapter |
| `The-Interdependency/metapat` | `86415a5368c1a1417c2b6731f19967a6b1fce6bb` | Optional semantic classification; never skill or metadata authority |

The pubskill starting head already pins and byte-checks the current two-skill
MSDMD slice from the required skill-lib commit. Do not repeat that repair or
rebase onto an unverified producer head.

Before editing, read in this order:

1. `pubskill-lib/AGENTS.md`
2. `pubskill-lib/README.md`
3. `pubskill-lib/HANDOFF.md`
4. `pubskill-lib/SOURCE.md`
5. `pubskill-lib/docs/skill-source-sync.md`
6. `skill-lib/AGENTS.md`
7. `skill-lib/msdmd/SKILL.md`
8. `skill-lib/msdmd/references/implemented-readers.md`
9. `skill-lib/msdmd/references/metadata-conventions.md`
10. `metapat/DOMAIN_RESTRAINT.md` and `metapat/docs/structural-recurrence.md`

## Result required

At the accepted head, a clean checkout must provide all of the following:

1. A source-pinned copy of every current `skill-lib` skill package and its
   referenced shared doctrine/resources. The current catalog contains 44
   skills. Propagation must use `skill-lib/tools/propagate_skills.py` from the
   exact producer commit with its default all-skills selection; do not hand-copy
   or independently rewrite canonical skill files.
2. A machine-readable catalog that lists each skill's name, description, kind,
   status, path, exact source commit and byte digest. Catalog output must be
   derived from the vendored bytes and `skills.json`, never maintained by hand.
3. The actual schema-2 MSDMD collector and every reader/runtime declared by the
   producer's executable support matrix. Missing optional runtimes must produce
   explicit unsupported-reader diagnostics, not empty success.
4. A hosted read-only API and an MCP server that let a client retrieve skills,
   collect repository metadata, and query the resulting collection.
5. Compatibility for the existing static `/inspect` endpoint and schema-1
   findings contract. Schema 1 remains the static-inspector response; schema 2
   remains the native-capable MSDMD collection. Never coerce one into the other.
6. Optional METAPAT classification only through the bounded interface described
   below. Pubskill parity itself must work without METAPAT.

## What “equivalent to skill-lib” means

Parity is tested along four separate dimensions:

### 1. Source parity

- Every catalogued skill directory under `.agents/skills/` is byte-identical to
  the corresponding directory at the pinned `skill-lib` commit.
- Referenced shared doctrine is present and byte-identical.
- The installed catalog includes the producer `skills.json` identity and a
  digest of the complete propagated set.
- Repo-local pubskill code remains pubskill-owned. Propagation transfers source
  bytes, not implementation authority.

### 2. Metadata parity

- Pubskill can run the same `msdmd.collect` schema-2 collector over supplied
  source bytes/worktrees using the producer implementation.
- Native declarations, supplemental MSDMD blocks, provenance, qualified IDs,
  qualified edges, conflicts, coverage, reader runs, diagnostics and `hmmm`
  survive serialization.
- The service follows `implemented-readers.md` exactly. A catalogued convention
  is not advertised as implemented unless its shipped fixture passes.
- Collection never imports or executes inspected application code.

### 3. Retrieval parity

- A client can list the full catalog, retrieve a skill and its referenced
  resources, inspect the exact producer/consumer identities, and query facts or
  declarations without cloning `skill-lib` itself.
- Returned skill content always includes its source commit and content digest.
- Skill trigger descriptions remain canonical. Pubskill may rank matching
  skills, but must show the score/method and return candidates rather than
  silently declaring one skill authoritative.

### 4. Execution parity

- Only entries explicitly marked `runnable` with a declared runner may be
  executed. At the required producer pin, `msdmd` is runnable and
  `repo-audit-repair` is a contract; the other skills are procedural or
  metadata guidance.
- Serving or retrieving a procedural skill is parity. Pretending to have
  executed its instructions is not.

## Required architecture

Keep one canonical engine and two transports:

```text
pinned skill-lib bytes
        |
        v
pubskill catalog + MSDMD application service
        |                         |
        v                         v
versioned HTTP API          MCP Streamable HTTP
```

Do not make the MCP server scrape the website, shell out to an unrelated CLI,
or maintain a second catalog. HTTP and MCP adapters must call the same typed
application functions.

Suggested new package boundaries:

```text
src/pubskill_lib/
  identity.py          # producer, consumer, catalog and optional METAPAT pins
  catalog.py           # derive/list/retrieve exact canonical skill packages
  collections.py       # invoke and validate canonical MSDMD schema-2 collection
  queries.py           # read-only filtering over a validated collection
  metapat_adapter.py   # optional, exact-pin and digest checked
  api.py               # transport-neutral application functions
  mcp_server.py        # MCP 2025-11-25+ Streamable HTTP adapter
```

Names may change to fit the repository, but the boundaries must remain visible.

## Public HTTP surface

Retain:

- `GET /`
- `POST /inspect`
- the current `410` responses for retired paid-audit endpoints

Add a versioned read-only surface equivalent to:

- `GET /v1/identity`
- `GET /v1/skills`
- `GET /v1/skills/{name}`
- `GET /v1/skills/{name}/resource?path=...`
- `POST /v1/msdmd/collect`
- `POST /v1/msdmd/query`
- `POST /v1/skills/resolve`
- `POST /v1/metapat/recurrence` only when the optional adapter is enabled

Exact request/response schemas belong in checked-in JSON Schema or typed models.
Reject unknown fields at trust boundaries. Responses must identify schema
version, producer commit, pubskill build identity, input identity and applicable
diagnostics.

## Amazon hackathon MCP surface

Implement MCP specification `2025-11-25` or later over Streamable HTTP. Expose
small, composable tools backed by the same application layer:

- `pubskill_identity`
- `pubskill_list_skills`
- `pubskill_get_skill`
- `pubskill_get_resource`
- `pubskill_collect_metadata`
- `pubskill_query_metadata`
- `pubskill_resolve_skills`
- `pubskill_classify_recurrence` only when METAPAT is enabled

The hackathon-qualified vertical slice is:

1. user or agent supplies a public repository and an exact revision;
2. pubskill collects native-first schema-2 MSDMD without executing target code;
3. the client asks which canonical skills apply and why;
4. pubskill returns source-linked facts, candidate skills, unresolved coverage
   and exact provenance;
5. the client retrieves the selected skill/resources and can replay the query.

This is “msdmd as a service.” Alexa+ is a client surface, not the authority and
not the metadata engine.

## Repository acquisition and safety

The current hosted service clones public HTTPS repositories. Preserve the host
allowlist and strengthen the acquisition boundary before schema-2 collection:

- require an exact revision or return the resolved immutable commit in every
  receipt;
- disable submodule recursion, Git hooks, credential helpers and LFS smudging;
- reject credentials, alternate ports, query strings, fragments, path escapes,
  local/file/ssh protocols and redirects outside the allowlist;
- impose request, repository-byte, file-count, per-file, wall-time and output
  limits;
- never install target dependencies, execute target code, expand templates,
  follow repository instructions or expose environment secrets;
- use an isolated temporary worktree and delete it after the receipt is built;
- treat symlink escapes, undecodable required inputs, parser failures and
  unavailable runtimes as explicit diagnostics.

If the existing simple HTTP server cannot enforce these boundaries cleanly,
replace the transport implementation while preserving the application contract
and `/inspect` compatibility.

## METAPAT boundary

METAPAT is optional and narrower than general inference.

Use the exact pinned package to expose current catalog identity and
`adjudicate_recurrence(RecurrenceEvidence)`. Accept only fully typed evidence
with the current METAPAT catalog version/digest and required module bindings.
Return the complete decision, including unresolved inputs and all three transfer
flags.

The adapter must enforce:

- `semantic_transfer = false`
- `proof_status_transfer = false`
- `measurement_status_transfer = false`
- incomplete mapping, replay or ancestry evidence produces `HMMM`
- `SAME_STRUCTURE` requires the explicit equivalence-proof identity required by
  METAPAT; pubskill cannot manufacture or verify that proof

Do not use METAPAT to infer imports, ownership, dependencies, runtime behavior,
skill applicability or verification from textual resemblance. Those come from
native metadata, declared skill descriptions, source-linked relations and real
checks. METAPAT may classify a supplied cross-domain recurrence after those
facts exist; it cannot fill missing evidence.

Do not copy METAPAT canon into pubskill or edit it locally. Add it as an optional
exact-version/commit consumer with a fail-closed identity check. A catalog
rotation must make a stale adapter fail until explicitly rebound.

## Implementation sequence

### Phase A — establish parity manifest

1. Create a feature branch from the required pubskill head.
2. Run canonical propagation from the detached required skill-lib commit with
   the default all-skills selection.
3. Replace the current two-skill-only assertions with full-catalog parity tests.
4. Update `SOURCE.md`, `_source.json`, `.agents/skills/README.md`, the canonical
   checkout in `skill-source.yml`, and the cross-repository work graph together.
5. Generate a deterministic catalog manifest and test its byte replay.

### Phase B — hosted MSDMD application layer

1. Package the collector/readers without forking their implementations.
2. Add typed identity, collection and query functions.
3. Preserve schema-1 inspection separately.
4. Add bounded public-repository acquisition and receipt generation.
5. Add a deployment image containing every required reader runtime; optional
   runtime absence must still be represented truthfully in local/minimal builds.

### Phase C — HTTP and MCP adapters

1. Add versioned HTTP endpoints over the application layer.
2. Add MCP Streamable HTTP transport with tool schemas and capability discovery.
3. Provide a local simulator/client so the server can be demonstrated without
   gated Alexa+ developer tooling.
4. Add one end-to-end fixture repository and record exact, replayable output.

### Phase D — bounded METAPAT adapter

Implement only after Phases A–C pass. Add the optional adapter and tests proving
pin mismatch rejection, `HMMM` on incomplete evidence, and zero status transfer.
If no real recurrence use case requires it for the submission, leave it optional
rather than making parity depend on it.

### Phase E — release and deployment evidence

1. Select a new semantic version (at least `0.3.0`); never move or recreate
   `v0.2.0`.
2. Reproduce wheel/sdist artifacts under the existing two-umask gate.
3. Install the exact built wheel in a clean environment and run the API/MCP
   integration suite from outside the source tree.
4. Build the container twice and record source, dependency, image and catalog
   digests.
5. Deploy only through the existing authorized pubskill deployment path.
6. Verify the live identity endpoint and one bounded fixture collection against
   the accepted local receipt. A local build, merged PR and live deployment are
   three different states; report them separately.

## Required tests

At minimum, add executable checks for:

- all 44 skill packages and referenced doctrine byte-match the pinned producer;
- removed/added producer skills make the parity gate fail until repinned;
- catalog generation is deterministic and rejects duplicate names/paths;
- retrieval rejects traversal, symlink escape and unlisted resources;
- schema-2 collection exercises every reader marked implemented in the producer
  matrix and reports every missing optional runtime;
- inspected target code is never executed (sentinel fixtures for each code
  reader family);
- duplicate native/MSDMD IDs remain qualified or conflict-visible;
- source-qualified edge endpoints never collapse equal local IDs;
- malformed fences, parse failures and stale projections fail strict mode;
- collection and query output preserve source digest, revision and diagnostic
  standing;
- `/inspect` output remains schema 1 and backward compatible;
- HTTP and MCP tool schemas reject unknown/mistyped fields;
- MCP initialization, tool listing and every tool call work over Streamable HTTP;
- time, byte, file-count and output limits fail closed with useful diagnostics;
- logs redact authorization headers, provider keys, repository credentials and
  submitted private content;
- METAPAT identity mismatch fails; incomplete evidence returns `HMMM`; every
  recurrence decision retains false transfer flags;
- clean wheel/sdist/container replay succeeds without importing source from the
  developer checkout.

## Acceptance commands

Keep existing gates, then add explicit parity/service/MCP gates. The final PR
description must list the exact commands actually run. The minimum combined
gate should resemble:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[service,readers,test]'
python -m unittest discover -s tests
python -m pytest -q
python -m pubskill_lib.audit examples/neglected-repo --out /tmp/findings.json
python -m msdmd.collect --root examples/metadata-repo \
  --repo fixture/metadata-repo --snapshot-identity --strict --json \
  > /tmp/collection.json
python -m pubskill_lib.mcp_server --self-test
python tools/build_release.py --out /tmp/pubskill-release-a
python tools/build_release.py --out /tmp/pubskill-release-b
diff /tmp/pubskill-release-a/SHA256SUMS /tmp/pubskill-release-b/SHA256SUMS
```

Adapt command names to the implementation, but do not weaken what they prove.

## Deliverables

1. A focused `pubskill-lib` pull request based on the required starting head.
2. Updated public documentation distinguishing catalog retrieval, static
   inspection, schema-2 collection, query, MCP transport and optional METAPAT.
3. Generated parity/catalog/work-graph receipts with exact producer identities.
4. Test evidence for clean source, wheel, sdist and container runs.
5. A local MCP demonstration script suitable for the Amazon submission video.
6. A deployment handoff containing required environment variables, resource
   limits, health/identity probes, rollback target and live-verification steps.
7. A final status using only `SURVIVED`, `FALSIFIED`, `UNRESOLVED`, `BLOCKED` or
   `DEPRECATED`, with every claim tied to a commit, run or receipt.

## Stop conditions

Stop and report rather than improvising if:

- either required producer or consumer identity moved before work began;
- full propagation exposes licensing material that cannot lawfully be
  redistributed under pubskill's current license;
- a skill resource cannot be included without copying secrets or private data;
- parity would require executing inspected repository code;
- a schema migration would make schema-1 and schema-2 identities ambiguous;
- METAPAT would be used to replace missing evidence or transfer proof,
  measurement, geometry or domain status;
- production deployment requires credentials or authority unavailable to the
  executor.

Record each stop as `hmmm` or `BLOCKED` with exact evidence. Do not convert it
into success prose.

## Final boundary

`skill-lib` owns the canonical skills and MSDMD implementation. `pubskill-lib`
owns public packaging, retrieval, hosting and MCP transport. METAPAT may classify
supplied structural recurrence under its own exact catalog identity. None of
these roles transfers semantic truth, verification, measurement, geometry or
deployment authority to another repository.
