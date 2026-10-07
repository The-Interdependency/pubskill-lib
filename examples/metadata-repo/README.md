# metadata-repo

A small fixture repository that exercises the schema-2 MSDMD collector
without executing any of its code. It exists so the hosted collection path has
one end-to-end, byte-replayable example: a client supplies this repository and
an exact revision, pubskill collects native-first schema-2 metadata, and the
resulting collection matches the version-pinned expected files in
`examples/metadata-repo-expected/` (one per supported interpreter, because the
Python reader records the running grammar version).

The fixture deliberately keeps:

- a Python module with a documented symbol and one supplemental `CONTRACTS`
  MSDMD block,
- a Python project manifest (`pyproject.toml`),
- an npm package manifest (`package.json`),
- a GitHub `CODEOWNERS` file,
- and no code that writes to the filesystem or the network.

Nothing in this directory is ever executed by the collector.
