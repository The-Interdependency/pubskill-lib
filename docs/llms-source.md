# LLMS source for pubskill-lib

Owning `LLMS` declarations for the shipped block-only publisher. Edit this file,
then regenerate root `llms.txt`. Do not hand-edit the generated file.

# === LLMS ===
# id: project_overview
#   content: Public distribution of skill-lib. Clone this repo when you want a command that inspects a local repository and writes findings. The full catalog, org doctrine, and unfinished skills stay in skill-lib. This repo is the subset a stranger can run.
#
# id: key_definitions
#   skill-lib: The skill catalog. This repository is not the skill catalog.
#   pubskill-lib: Public distribution of skill-lib; distribution plus public CLI plus fixtures.
#   source pin: The exact canonical skill-lib commit used for the vendored public skill slice.
#   hmmm: Unresolved work stays hmmm. Do not write success prose over missing runners.
#   msdmd: Module Self-Declared Metadata in Markdown — native-first collection of metadata already expressed by code, documentation, manifests, schemas, tooling, and evidence formats, with MSDMD blocks only for otherwise unexpressed information.
#   manifest: Living-spec generator. Derives observable repo facts from pyproject.toml and the file tree into a machine-owned block inside CLAUDE.md, and can fail on drift in --check mode.
#   llms-build: LLM instruction publication from owning metadata; the shipped runner generates root llms.txt from LLMS blocks, while native-reader integration remains a contract.
#
# id: architecture_summary
#   content: - Vendored public skills live under `.agents/skills/` and are pinned in SOURCE.md and src/pubskill_lib/_source.json.
#     - The inspect and examiner CLIs live in src/pubskill_lib. The wheel's inspector and Examiner interfaces remain the public package contract.
#     - The llms-build stdlib runner lives at repo-root llms/ so `python -m llms.build` works. skill-lib's own llms/metadata.py is not shipped.
#     - examples/neglected-repo is the release-gate fixture for the inspect CLI.
#
# id: usage_rules
#   content: - Read README.md, AGENTS.md, and SOURCE.md before changing this repository.
#     - Do not invent a second msdmd, a second findings schema, or a second audit doctrine.
#     - Do not copy org-only skills into this tree.
#     - Do not stamp verified unless a gate was actually re-run.
#     - Write unresolved or missing values as hmmm.
#     - Vendored skills must cite the skill-lib SHA in SOURCE.md and in `.agents/skills/README.md`.
#     - If skill-lib and this repo disagree, skill-lib wins for skill text; this repo wins for CLI entrypoint, fixtures, and public README.
#     - Edit source LLMS blocks before regenerating llms.txt. Do not infer or expand declared key definitions.
# === END LLMS ===
