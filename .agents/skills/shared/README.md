# skill-lib

A portable library of agent skills built on **msdmd** — Module Self-
Declared Metadata in Markdown. MSDMD consumes metadata already expressed in
native code, documentation, manifests, schemas, tooling, and evidence formats;
its own comment blocks supplement information not already expressed adequately.
The [foundational skill](msdmd/SKILL.md) and
[convention catalogue](msdmd/references/metadata-conventions.md) define the
native-first contract. The schema-2 collector now integrates supported native
source/document readers through the versioned reader registry, while the
universal MSDMD-block parser remains available for supplemental declarations.
Recognized unsupported inputs stay visible as explicit unknowns rather than being
treated as implemented readers. Unrecognized metadata dialects are not evidence of
complete inspection.

Licensed under MPL-2.0 (relicensed from MIT; weak copyleft — embed anywhere,
changes to these files must be published). The canonical install path inside a
consuming repo is `.agents/skills/<skill-name>/`; every target repo in
The Interdependency follows this convention (see
[`ORG_DISTRIBUTION.md`](ORG_DISTRIBUTION.md)). Other paths like
`.skills/` or `.local/skills/` also work as long as your agent harness
walks them.

Agents consuming this lib should start at
[`AGENTS.md`](AGENTS.md); a machine-readable index of skills is at
[`skills.json`](skills.json). Root LLM-facing instructions are generated
into [`llms.txt`](llms.txt) from self-declared `LLMS` blocks.

## What's inside

| Skill | Purpose |
|---|---|
| [`msdmd/`](msdmd/SKILL.md) | The foundational native-first metadata contract: convention discovery, provenance, conflicts, information coverage, and supplemental block syntax. The schema-2 collector integrates native source/document readers with qualified identities, required-fact policies and explicit unknowns; Python module projections share its attachment reader. |
| [`doc-build/`](doc-build/SKILL.md) | Applies native-first msdmd to documentation comments and source-linked documents; supplemental `DOCS` entries cover remaining obligations. Reader support and missing information stay distinct. |
| [`cap-build/`](cap-build/SKILL.md) | Consumes native signatures, exports and API schemas; supplemental `CAPABILITIES` entries add otherwise unexpressed intent. Declared surfaces are not verified behavior. |
| [`deps-build/`](deps-build/SKILL.md) | Consumes native imports, manifests and build metadata at their owning scopes; supplemental `DEPENDENCIES` entries add remaining architectural intent. |
| [`owner-build/`](owner-build/SKILL.md) | Consumes provider-specific native ownership/review rules; supplemental `OWNERS` entries add missing stewardship information. Review assignment does not automatically establish operational ownership. |
| [`test-build/`](test-build/SKILL.md) | Consumes supported native obligations and witnesses or supplemental `CONTRACTS` / `CHECKS`; preserves source/test ownership, explicit linkage and no-exec audits. Native evidence readers remain a contract. |
| [`meta-module-build/`](meta-module-build/SKILL.md) | Consumes native manifests, schemas and planning records before requesting supplemental `MODULE_BUILD` information. Boundary, test, rollout and rollback obligations remain required. |
| [`risk-boundary-build/`](risk-boundary-build/SKILL.md) | Consumes native permission, configuration and effect declarations before supplemental `BOUNDARIES` information. Declared controls are not verified enforcement. |
| [`ratios/`](ratios/SKILL.md) | Applies msdmd → module composition ratio verification. Each computer-covered source module records `loc_comments`, `imports_exports`, and `calls_definitions` at its opening and closing source boundaries (not a fenced block; a valid line-1 shebang may precede opening RATIOS; JSON/Markdown are out of scope); the reference `ratios_check.py` recomputes Python values and checks for drift and misplacement. |
| [`manifest/`](manifest/SKILL.md) | Living-spec generator (msdmd family). Derives observable repo facts from `pyproject.toml` + the tree and splices them into a machine-owned marked block in `CLAUDE.md`, with a CI `--check` drift gate. |
| [`llms-build/`](llms-build/SKILL.md) | Native-first instruction-publication contract; shipped `python -m llms.build` still generates root `llms.txt` from existing `LLMS` blocks only. Native readers remain unimplemented. |
| [`typed-meta-frontend/`](typed-meta-frontend/SKILL.md) | Applies msdmd-aligned backend metadata → TypeScript self-building frontend. The UI discovers every module, displays its living spec, exposes every declared editable field, preserves read-only reasons and `hmmm`, and tests metadata-to-field coverage. |
| [`canon/`](canon/SKILL.md) | Canonical-source and doctrine maintenance. Helps agents decide what is source-backed canon, proposed canon, or `hmmm` before changing skills or org doctrine. Independent of msdmd. |
| [`domain-claims/`](domain-claims/SKILL.md) | Domain-first lexical and semantic governance. Before a word becomes a theorem term, ontology primitive, schema field, encoding label, or other control surface, establish the domain-qualified sense, scope, exclusions, collision status, and standing that later provenance may attach to. Independent of msdmd. |
| [`visitor-intro/`](visitor-intro/SKILL.md) | Onboarding tour skill. Lets any agent give a coherent, repo-aware orientation to newcomers landing at any The-Interdependency repo, without inventing org-level facts. Independent of msdmd. |
| [`adaptive-elicitation/`](adaptive-elicitation/SKILL.md) | Adaptive context-first interviewing. Harvests known context before asking, asks one neutral question at a time, consumes volunteered facts, adapts the next question to the answer, and preserves unresolved material as `hmmm`. Independent of msdmd. |
| [`char-compress/`](char-compress/SKILL.md) | Skill-lib-owned bone/flesh context compression (historical text-stack notation, not current UCNS mathematics) for agent handoff and skill writing. Preserves irreducible flesh, frozen bones, transforms, and `hmmm`; drops only safely regenerable scaffold. Independent of msdmd. |
| [`agent-instantiation/`](agent-instantiation/SKILL.md) | Methodology for instantiating, forking, running, merging, and retiring agents in `a0` and its mirror `a0ucns`. Spawn via the `sub_agent_spawn` tool → executor; fork/merge `PCNAEngine` instances via `InstanceMerge`; compose identities; honor spawn caps and write-route gating. `a0-betatest` diverges (per-user native-ZFAE) and is out of scope. Independent of msdmd. |
| [`a0p-instancing/`](a0p-instancing/SKILL.md) | Peer of `agent-instantiation` for a0-betatest (a0p), whose model diverges: agents are per-user CRUD `AgentInstance` entities bound to a `CharacterSheet`, each owning a trained native ZFAE weight bank; no spawn/fork/merge — only volatile sub-context memory. Covers create→train→readiness-gate→mode inference→sentinel/override→safetensors checkpoint. Independent of msdmd. |
| [`plain-lens/`](plain-lens/SKILL.md) | Plain-language, multi-lens companion views of dense canonical text — easier on-ramps that do not replace or talk down to the source. Domain/audience/role lens selectors, progressive-disclosure reading UX, static fallback for dynamic pages, and EDCM-style body-vs-footnote tension readings. Independent of msdmd. |
| [`thought-lens/`](thought-lens/SKILL.md) | Translation compiler for raw, context-heavy thought. Recovers a claim kernel before rendering audience/surface-specific language, preserves claim force and operators, introduces coined terms only after their ordinary meaning lands, and back-checks for fidelity and remaining context debt. Independent of msdmd. |
| [`meta/`](meta/SKILL.md) | Consultation router for current METAPAT. Retrieves the authoritative repository when a conceptual relation, distinction, boundary, transformation, scale, or cross-domain correspondence would constrain downstream work; carries no frozen METAPAT doctrine here. Independent of msdmd. |
| [`gonol-build/`](gonol-build/SKILL.md) | UCNS gonol objects/constructors/geometry + Stack language-construction research discipline. Preserves closure, atomic participation, exact source/occurrence identity, provenance, honest `hmmm`, and scoped replay; EDCM is measurement/evaluation only. Independent of msdmd. |
| [`ucns-option-selection/`](ucns-option-selection/SKILL.md) | Fail-closed UCNS option-selection rubric. Freezes scope, candidates, authority, gates, policies, and evidence boundaries; requires complete execution, falsification, replay, purpose-relative comparison, non-transfer, rollback, and explicit ratification; refuses compensating scores and universal promotion from local evidence. Independent of msdmd. |
| [`epac-selection-display/`](epac-selection-display/SKILL.md) | Evidence-bound EPAC target selection and display. Resolves an exact provisional source, target, receipt, and available renderer; preserves standing, `selection_effect`, nonclaims, sealed-comparison boundaries, and `hmmm`; and keeps the WebMCP surface a read-only repository-and-skill handoff rather than an EPAC executor. Independent of msdmd. |
| [`the-interdependency/`](the-interdependency/SKILL.md) | Workflow and protocol for code building, researching, GitHub maintenance and updates, EDCMBONE transcript assembly for analysis, and anything that touches The Interdependency organization or The Interdependent Way projects. Enforces structure preservation (neurodivergence-compatible), mandatory usage guidance in all artifacts, framework-aligned EDCMBONE analysis, and org-standard GitHub hygiene. Independent of msdmd. |
| [`interdependent-work-graph/`](interdependent-work-graph/SKILL.md) | Cross-repository coordination doctrine. Resolves exact participating commits, authority roles, work relations, non-transfer boundaries, shared stack manifests, and validation/materialization order before a stack-level task is reduced to one repository. Independent of msdmd. |
| [`stack-update/`](stack-update/SKILL.md) | Fail-closed structural update protocol for `The-Interdependency/stack`. Makes participant, authority, relation, lifecycle, placement, manifest, and BASE changes one coherent transaction and requires a deterministic consistency gate before merge. Independent of msdmd. |
| [`project-incubation-graduation/`](project-incubation-graduation/SKILL.md) | Incubation-to-independent-project graduation doctrine. Qualifies emergent candidates, preserves provenance through extraction, creates a new implementation-authority boundary, releases the artifact, and requires the former forge to reconsume the release before graduation is complete. Independent of msdmd. |
| [`distributed-publication/`](distributed-publication/SKILL.md) | Provenance-bearing publication from distributed source owners. Builds ordered textbooks, reports, standards, corpora, archives, and public reading surfaces from exact source identities while preserving source-local licenses and statuses, fail-closed production retrieval, explicit fallback, correction routing, and public build provenance. Loads with `interdependent-work-graph`. Independent of msdmd. |
| [`website-builder-journal/`](website-builder-journal/SKILL.md) | Append-only builder-journal contract for `interdependentway.org`. Every website modification transaction adds a model-authored entry with date, time, exact runtime model, and no editorial constraint beyond sufficient explication; the public journal remains a collapsible tree. Independent of msdmd. |
| [`loop-eng/`](loop-eng/SKILL.md) | Loop engineering for designing closed feedback cycles (Discover→Plan→Execute→Verify→Iterate), single-agent and fleet loops with subagent maker/checker separation, and automated verify-iterate workflows. Integrates with a0p/AIMMH orchestration, EDCMBONE Verify stages, skill-lib Skills, and structure-preserving practices. Independent of msdmd. |
| [`fresh-making/`](fresh-making/SKILL.md) | Deterministic restoration of derived-artifact consistency from exact inputs. Computes minimal affected closure, verifies outputs independently of executors, records replayable receipts, and keeps unknown freshness visible as `hmmm`. Independent of msdmd. |
| [`action-calibration/`](action-calibration/SKILL.md) | Chooses the smallest decisive action versus the maximal coherent program, with complete cost vectors, three-outcome branching, frozen escalation rules, and explicit prerequisite/containment boundaries. Independent of msdmd. |
| [`repo-audit-repair/`](repo-audit-repair/SKILL.md) | Evidence-led repository auditing and authorized repair from exact starting identity through classified findings, truthful gates, owning-layer fixes, and authoritative terminal verification. Independent of msdmd. |
| [`skill-build/`](skill-build/SKILL.md) | Skill authoring and compliance workflow. Guides agents through the question set for creating or revising skills, choosing metadata-block vs procedural shape, designing individualized test suites, and bringing existing skills into a shared compliance pattern. Independent of msdmd. |
| [`skill-usage/`](skill-usage/SKILL.md) | Evidence-bearing local usage maturity. Counts material skill invocations, preserves unknown outcomes as `hmmm`, and separates nominal exposure from effective maturity across experimental, field-test, operational, reliable, and daily-use designations. Independent of msdmd. |
| [`ssh-automation/`](ssh-automation/SKILL.md) | Fail-closed SSH scripting and terminal-delivery doctrine. Preserves endpoint identity, verified host trust, explicit authentication, local/remote shell boundaries, stdin and PTY semantics, bounded retries, idempotent activation and rollback, and child-shell containment for one-box Cloud Shell pastes. Independent of msdmd. |
| [`vm-mcp/`](vm-mcp/SKILL.md) | Private VM MCP control plane. Gives MCP-capable agents bounded VM file/shell contact without exporting SSH credentials: loopback-only Streamable HTTP, non-root execution, systemd host-write confinement, cloud-metadata denial, read-only-first rollout, and explicit `hmmm` around client tunnel/write capability. Independent of msdmd. |
| [`sql-queries/`](sql-queries/SKILL.md) | Correct, performant SQL across major warehouse dialects (Snowflake, BigQuery, Databricks, PostgreSQL): dialect reference, CTE/window patterns, optimization, debugging checklist. Imported from `anthropics/knowledge-work-plugins` (Apache-2.0); see `ATTRIBUTION.md`. Independent of msdmd. |
| [`statistical-analysis/`](statistical-analysis/SKILL.md) | Statistical methods for analyses: descriptive stats, assumption checks, hypothesis testing, outlier detection, effect sizes, and plain-language interpretation. Imported from `anthropics/knowledge-work-plugins` (Apache-2.0); see `ATTRIBUTION.md`. Independent of msdmd. |
| [`explore-data/`](explore-data/SKILL.md) | Dataset profiling: shape, grain, null/duplicate/quality checks, distributions, and which dimensions and metrics merit analysis. Imported from `anthropics/knowledge-work-plugins` (Apache-2.0); see `ATTRIBUTION.md`. Independent of msdmd. |
| [`validate-data/`](validate-data/SKILL.md) | Pre-share QA of analyses: methodology, accuracy, and bias checks; reproduce key numbers independently; attack conclusions before sign-off. Imported from `anthropics/knowledge-work-plugins` (Apache-2.0); see `ATTRIBUTION.md`. Independent of msdmd. |
| [`data-visualization/`](data-visualization/SKILL.md) | Effective chart-building doctrine with Python (matplotlib, seaborn, plotly): chart-type selection, honest encoding, accessibility. Only `SKILL.md` is imported from `anthropics/knowledge-work-plugins@94e1a08`; the whole `SKILL.md`, including its local additions, is Apache-2.0. The four information-design extension files (skill-lib `868de86`) are original under MPL-2.0; see `ATTRIBUTION.md`. Independent of msdmd. |

## Support this work

skill-lib is MPL-2.0 and free to embed. If msdmd or these skills saved you
time, effort, or energy, you can route some of it back:
**[Cash App](https://cash.app/$wayseer00)**.

The work asks no faith — run the checkers and watch them pass. What support
funds is continuation: the checkers stay maintained, the skill families keep
growing, and the conventions stay free for the next person who needs them
early enough to matter.

## Install as a Claude Code plugin marketplace

This repo doubles as a Claude Code plugin marketplace
(`.claude-plugin/marketplace.json`). From any Claude Code session:

```shell
/plugin marketplace add The-Interdependency/skill-lib
/plugin install skill-lib@skill-lib
```

Skills load namespaced (e.g. `/skill-lib:msdmd`). The vendored-copy install
path (`.agents/skills/<skill-name>/`) remains the canonical convention for
org repos; the marketplace route is for direct use and outside adopters.

## Install as a Codex plugin

The repository root is a Codex plugin. Its
`.codex-plugin/plugin.json` exposes generated adapters under `skills/`.
Each adapter loads its canonical root `*/SKILL.md`, keeping the existing root
skill as the sole doctrine source while making every registered skill
installable through Codex.

Canonical `SKILL.md` frontmatter is the trigger authority. `skills.json` repeats
each description only as a checked index field; the drift gate requires exact
agreement, and generated adapters read the canonical frontmatter directly.

During local plugin testing, place this repository behind a Codex local
marketplace entry, install `skill-lib`, then begin a new conversation. The
installed plugin exposes every skill in `skills.json`.

Usage maturity is local and contains no prompt text. Each material skill use
loads `skill-usage`, which records into `$PLUGIN_DATA/usage.json`:

```bash
python "$PLUGIN_ROOT/tools/skill_usage.py" record canon \
  --state "$PLUGIN_DATA/usage.json" \
  --outcome hmmm

python "$PLUGIN_ROOT/tools/skill_usage.py" status \
  --state "$PLUGIN_DATA/usage.json"
```

Outside an installed plugin, omit `--state` to use
`.skill-lib/usage.json`. See `skill-usage/SKILL.md` for the
designation thresholds, quality caps, critical-failure handling, and the
documented automation boundary.

After changing `skills.json` or canonical skill metadata, rebuild and check the
Codex adapters:

```bash
python tools/build_codex_plugin_skills.py --apply
python tools/build_codex_plugin_skills.py --check
```

## VM coding-agent launcher

The canonical `ai.sh` launcher lives at `tools/ai.sh`. It runs on Termux,
reaches the `a0` VM through the SSH host alias `a0`, and manages the remote
`a0` tmux session. Install it into the caller PATH without copying the
implementation:

```bash
bash tools/install_ai.sh
```

On Termux the installer symlinks `ai.sh` into `$PREFIX/bin`; elsewhere it falls
back to `~/.local/bin/ai.sh`. `ai.sh status` reports remote pane state,
`ai.sh restart deepcode` repairs a missing/dead DeepCode window, and pane output
persists on the VM under `~/.local/state/a0/logs`. `ai.sh keys` only propagates
already-present VM login-environment keys into tmux and reports
`present`/`missing`, never values.

## Maintenance tools

Pure-stdlib helper scripts live in [`tools/`](tools/README.md). The small
`llms/` package exists only to provide the `python -m llms.build` command.

```bash
python tools/check_skill_lib_drift.py --warnings-fail
python tools/check_skill_compliance.py --warnings-fail
python tools/char_compress_check.py
python tools/propagate_skills.py ../target-repo          # dry-run
python tools/propagate_skills.py ../target-repo --apply  # copy local files
python -m llms.build --root . --out llms.txt             # dry-run
python -m llms.build --root . --out llms.txt --apply     # write generated file
python -m llms.build --root . --out llms.txt --check     # drift gate
```

The drift checker compares skill directories, canonical frontmatter,
`skills.json`, `README.md`,
`ORG_DISTRIBUTION.md`, `AGENTS.md`, and `CLAUDE.md`. The skill compliance
checker also rejects explicitly superseded vendored skills. The skill compliance
checker enforces baseline `skill-build` invariants and reports softer
normalization guidance as warnings. The propagation helper updates canonical
files in a checked-out target repo, preserves repo-local additions, and removes
retired canonical files only when the target's cited prior source proves their
identity. The char-compress runner
executes preservation fixtures for negation, quantifier, order, values,
statuses, secrets, `hmmm`, and unearned theorem/status leakage. The llms-build
runner generates the root `llms.txt` from `LLMS` blocks and can fail on drift in
`--check` mode.

|∆|Implementation status: this repo ships the universal msdmd parsers, the
schema-2 native-and-supplemental collector, a partial Python per-module metadata
reader, skill specifications, selected pure-stdlib helper tools, and the
`llms-build` runner. Most other application skills define runner contracts for
consuming repos; they do not ship standalone executors here unless a helper file
exists in that skill directory or package.| ∆|

## The core idea

**Consume declarations where they already live; do not demand a second copy.**
A docstring can own symbol documentation, a package manifest can own package
metadata, and a native ownership file can own review rules. MSDMD preserves
source identity and scope while making this information available to shared
collection consumers. Supplemental MSDMD blocks express remaining obligations.

Native-first coverage measures required information, not compulsory block
adoption. Missing blocks, genuinely missing information, unsupported readers,
conflicting declarations, and unverified behavior remain separate findings.
The affected application skills and their load-bearing descriptions apply the
same native-first coverage rule without removing their semantic obligations.

The universal parsers remain block readers for supplemental MSDMD blocks.
`msdmd/collect.py` defaults to schema 2 and integrates native source/document
facts through `msdmd/readers.py` while preserving unsupported conventions and
unknown fields as visible findings. The separate `msdmd/module_projection.py`
runner implements a bounded native slice for Python symbols, signatures,
decorators, docstrings, and structurally attached comments, using the versioned
`msdmd/module-projection.schema.json` JSONL format.
`skills.json` keeps the shipped collector discoverable as `runnable`, with
`runner_scope: native-and-supplemental`, while `native_ingestion` is separately
marked `implemented-subsets` with its exact supported scope. Cross-source
semantic reconciliation, build/compiler context, arbitrary language completeness,
and independent signature/evidence verification remain implementation work. See
the [helper limitations](msdmd/SKILL.md#shipped-helper-limitations).

## Supplemental block syntax (universal)

```python
# === <BLOCK_NAME> ===
# id: <unique_snake_case_id>
#   <field>: <value>
#   <field>: <value>
#
# id: <next_entry_id>
#   <field>: <value>
# === END <BLOCK_NAME> ===
```

The comment marker (`#`, `//`, `--`, etc.) is whatever's idiomatic for
the file's language. The fence text and field structure are identical
across languages. See [`msdmd/SKILL.md`](msdmd/SKILL.md) for the
authoritative spec.

## Extending the lib

Skills come in two kinds. Pick the right one for what you're adding.

**Metadata-block skills** apply `msdmd` to a domain's required information,
native owning sources and optional supplemental syntax (`doc-build`, `cap-build`,
`deps-build`, `owner-build`, `test-build`, `meta-module-build`, `risk-boundary-build`,
`ratios`, `manifest`, `llms-build`, and `typed-meta-frontend` are the existing examples).
The historical kind label does not make custom blocks compulsory.
To add one:

1. Define the required information and its owning scopes; inventory existing
   native conventions before requesting supplemental declarations.
2. Specify native-reader mappings and support boundaries. Pick a `<BLOCK_NAME>`
   only for information that needs an MSDMD-specific declaration.
3. Specify or implement extraction, reconciliation, information-coverage checks,
   and the executor. Keep the universal parser for the supplemental block path.
4. Author a `SKILL.md` with usage guidance, reader-status boundaries, and tests.

`test-build/` is the canonical worked example. `llms-build/` is the worked
example for a metadata-block skill that also ships a stdlib command module.

**Procedural skills** define an agent behaviour without an `msdmd`
block (`canon`, `domain-claims`, `visitor-intro`, `char-compress`, `agent-instantiation`,
`a0p-instancing`, `plain-lens`, `thought-lens`, `gonol-build`, `ucns-option-selection`, `epac-selection-display`, `meta`, `the-interdependency`,
`interdependent-work-graph`, `stack-update`, `project-incubation-graduation`, `distributed-publication`, `loop-eng`, `fresh-making`, `action-calibration`,
`repo-audit-repair`, `skill-build`, `skill-usage`, `ssh-automation`, and `vm-mcp`
are the existing examples). To add one:

1. Define when the skill loads (the `description` field in the YAML
   frontmatter is what your harness will read).
2. State the doctrine the skill enforces and the output shape it
   produces.
3. Author the `SKILL.md` as a self-contained behavioural spec — no
   block schema or executor is required.

Whichever kind you add, register it in [`skills.json`](skills.json)
and link it from the table above.

## Testing

Run the stdlib editorial test suite after changing skills or parser files:

```bash
python -m unittest discover -s tests
```

The suite checks skill/index consistency, skills.json semantics, per-skill
spec coverage, SKILL.md frontmatter, README skill links, collection-point
schema, generator, visualizer coverage, universal parser behavior, llms-build
behavior, and parser ratio bookends.

## Versioning and stability

- The msdmd block syntax is treated as a stable contract — breaking
  changes will go through a major version bump.
- Skill executors and field schemas live in their own SKILL.md files and
  may evolve independently.
- The universal parsers (`msdmd/parsers/universal.{py,ts}`) commit to
  pure-stdlib dependencies; you can copy them anywhere.
- The repo-level collection point shape lives at `msdmd/collection.ts`;
  consuming repos can import or copy it for `<reponame>_msdmd.ts`.
- A stdlib collection generator lives at `msdmd/collect.py` and can emit
  `<reponame>_msdmd.ts` from supported native facts and supplemental blocks.
- A stdlib Python native reader lives at `msdmd/module_projection.py` and emits
  deterministic per-module `.msdmd.jsonl` sidecars without executing source.
- A minimal Mermaid visualizer prototype lives at `msdmd/visualize.py` and
  can render collection edges and gaps.
- The `llms-build` runner lives at `llms/build.py` and can generate or check
  root `llms.txt` from `LLMS` blocks.
