# Hosted pubskill service

The hosted surface at `https://pubskill.interdependentway.org/` exposes two truthfully bounded products:

- **Inspection:** What obvious repository defects and unresolved static boundaries can be found without executing the repository?
- **Examiner:** What is actually in this codebase, how is it structured and documented, what can be measured safely, and where are the unresolved boundaries?

A versioned read-only API adds catalog retrieval and schema-2 MSDMD
collection/query over bounded public-repository acquisition:

- `GET /v1/identity`
- `GET /v1/skills`
- `GET /v1/skills/{name}`
- `GET /v1/skills/{name}/resource?path=...`
- `POST /v1/skills/resolve`
- `POST /v1/msdmd/collect`
- `POST /v1/msdmd/query`

`/v1/msdmd/collect` accepts `{"repo_url": "...", "revision": "..."}`; the
revision is optional, and every receipt returns the resolved immutable commit.
Acquisition is bounded: allowed HTTPS Git hosts only, no credentials, no
submodules, no git hooks, no LFS smudging, time/byte/file-count limits, and the
temporary worktree is deleted after the receipt is built. Target code is never
installed, executed, or instructed. Schema-1 `/inspect` and schema-2 MSDMD
collection remain separate contracts; neither is coerced into the other.

## MCP surface

`POST /mcp` speaks MCP Streamable HTTP (specification `2025-11-25`) as a
stateless JSON transport. The same application layer backs every tool; the MCP
adapter maintains no second catalog:

- `pubskill_identity`
- `pubskill_list_skills`
- `pubskill_get_skill`
- `pubskill_get_resource`
- `pubskill_collect_metadata`
- `pubskill_query_metadata`
- `pubskill_resolve_skills`

Requests must send `Accept: application/json, text/event-stream`. A local
client suitable for demonstrations (no Alexa+ tooling required):

```bash
python -m pubskill_lib.mcp_server --self-test
python tools/mcp_client.py --url http://127.0.0.1:8080/mcp
```

The end-to-end fixture `examples/metadata-repo` records exact, replayable
schema-2 collections in `examples/metadata-repo-expected/` (one per supported
interpreter); the test gate replays them byte for byte with
`--snapshot-identity --strict --json --check`.

## Optional METAPAT recurrence surface

METAPAT classification is optional and narrower than general inference. When
the adapter is enabled (an exact checkout of `The-Interdependency/metapat` at
the pinned commit, exposed via `PUBSKILL_METAPAT_ROOT`), pubskill adds:

- `GET /v1/metapat/catalog` — current METAPAT catalog version, digest, and
  required module bindings
- `POST /v1/metapat/recurrence` — adjudicate one fully typed
  `RecurrenceEvidence` record
- MCP tool `pubskill_classify_recurrence`

The adapter enforces the exact producer commit and the current catalog digest,
fails closed on pin mismatch, returns `HMMM` for incomplete mapping/replay/
ancestry evidence, never verifies an equivalence proof, and keeps
`semantic_transfer`, `proof_status_transfer`, and `measurement_status_transfer`
exactly `false`. METAPAT canon is never copied or edited in this repository.

## Repository inspection

Hosted inspection is **free**.

It clones one supported public HTTPS Git repository and runs the existing static inspector. The inspector may report repository identity, broken local README links, obvious CI no-ops, missing declared Python entry points, and directly referenced local script targets that are missing or escape the repository.

The hosted inspector does **not** install target dependencies, execute target repository code, run target tests, reproduce builds, inspect runtime behavior, or establish deployment health. A clean inspection result is therefore not a health certificate.

Usage:

```text
POST /inspect
Content-Type: application/json

{"repo_url":"https://github.com/owner/repo"}
```

Supported public HTTPS Git hosts are GitHub, GitLab, Bitbucket, Codeberg, and SourceHut.

## Retired paid audit surface

The previous `/audit`, `/checkout`, `/paid`, and `/operator/audit` endpoints are retired. They return HTTP 410 and point callers to `/inspect`.

Static inspection is not sold as a complete repository audit.

## Repository audit boundary

A true repository audit is not currently offered by the hosted service. It requires a separate execution boundary capable of running applicable repository gates in isolation and emitting reproducible receipts for the exact repository identity, commands, exit states, and artifacts observed.

That execution system does not yet exist in `pubskill-lib`; the missing capability remains `hmmm` rather than being represented by the static inspector.

## Examiner boundary

Structural examination does not require AI. AI is optional for narration. Hosted Examiner execution, metering, and pricing remain `hmmm` until measured against real repository runs; the hosted site must not imply those capabilities are already available.

## Deployment

The current inspection service requires no payment credentials or private operator bypass. Run the service with:

```bash
python service.py
```

The process listens on `PORT`, defaulting to `8080`.
