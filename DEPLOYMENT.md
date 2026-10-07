# Deployment handoff — pubskill-lib 0.3.0 parity source line

This handoff covers the hosted pubskill service (`service.py`) and its MCP
endpoint. Local build, merged PR, and live deployment are three different
states and must be reported separately.

## Required environment

| Variable | Required | Meaning |
|---|---|---|
| `PORT` | no | Listen port (default `8080`) |
| `PUBSKILL_SKILLS_ROOT` | no | Override the vendored skills root (default: repo `.agents/skills`, or packaged `pubskill_lib/_skills` in a wheel) |
| `PUBSKILL_METAPAT_ROOT` | only for METAPAT | Exact checkout of `The-Interdependency/metapat` at `86415a5368c1a1417c2b6731f19967a6b1fce6bb`; adapter fails closed otherwise |

No payment credentials, provider keys, or operator bypass are required by the
service. The deployment environment must provide `git`, `node`, and `npm` for
the container image build; the image installs the MSDMD reader runtimes.

## Resource limits (enforced by the service)

- request body: 1 MiB (HTTP API), 4 MiB (MCP)
- acquisition: HTTPS allowlist only; no credentials, ports, query strings, or
  fragments; git hooks, credential helpers, LFS smudging and submodules disabled
- fetch timeout 120 s, checkout timeout 60 s
- repository size 50 MiB, file count 20 000, per-file 2 MiB, collection output
  8 MiB characters
- collection timeout 180 s

## Health and identity probes

```bash
curl -s http://127.0.0.1:PORT/v1/identity | jq '.identity.producer, .identity.consumer, .identity.catalog.catalog_digest'
curl -s http://127.0.0.1:PORT/v1/skills | jq '.skill_count'      # must be 44
curl -s -X POST http://127.0.0.1:PORT/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
```

The identity probe must show the accepted producer commit
`9867ab33877f2b1f50f8a501cf379aa99360bd52` and the accepted consumer commit.
A local build is not a live deployment; report the exact state and commit.

## Rollback target

Roll back by redeploying the previously accepted `pubskill-lib` commit and its
already-built container/wheel artifacts. `v0.2.0` is immutable and is never
recreated or moved. Schema-1 `/inspect` and its 410 retired endpoints are part
of the rollback contract and must not change between deployments.

## Live verification steps

1. `GET /v1/identity` — verify producer/consumer/catalog identity against the
   accepted release receipt.
2. `GET /v1/skills` — 44 skills with the accepted catalog digest.
3. One bounded fixture collection:
   ```bash
   curl -s -X POST http://127.0.0.1:PORT/v1/msdmd/collect \
     -H 'Content-Type: application/json' \
     -d '{"repo_url":"https://github.com/octocat/Hello-World","revision":"<exact-sha>"}'
   ```
   Compare `receipt.repository.resolved_commit` to the requested revision and
   to the accepted local receipt. The schema must be
   `the-interdependency.msdmd-collection` version `2.0.0`.
4. Replay `examples/metadata-repo`:
   ```bash
   PYTHONPATH=.agents/skills python -m msdmd.collect \
     --root examples/metadata-repo --repo fixture/metadata-repo \
     --snapshot-identity --strict --json \
     --out examples/metadata-repo/expected-collection.json --check
   ```
5. MCP capability discovery: `tools/list` must expose exactly the enabled
   tools (plus `pubskill_classify_recurrence` only when METAPAT is enabled).

## Container build (recorded evidence)

Build the image twice and record source, dependency, image, and catalog
digests. The image installs `git nodejs npm`, the MSDMD Python reader
requirements, and `npm ci` for the TypeScript reader.
