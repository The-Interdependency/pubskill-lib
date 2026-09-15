# Hosted pubskill service

The hosted surface at `https://pubskill.interdependentway.org/` exposes two truthfully bounded products:

- **Inspection:** What obvious repository defects and unresolved static boundaries can be found without executing the repository?
- **Examiner:** What is actually in this codebase, how is it structured and documented, what can be measured safely, and where are the unresolved boundaries?

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
