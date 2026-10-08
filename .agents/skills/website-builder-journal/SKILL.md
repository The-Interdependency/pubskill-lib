---
name: website-builder-journal
description: Load this when any modification to The-Interdependency/The-Interdependency.github.io is planned or underway, including source, content, configuration, tests, workflows, dependencies, generated-contract code, or deployment paths. Every website change transaction must append at least one By the builder entry recording date, time, and the exact runtime model; the model chooses the subject and writes no more than needed to explicate it. Do not load for read-only inspection that changes no website file.
---

# website-builder-journal — every build leaves a builder trace

Use this procedural skill before changing `The-Interdependency/The-Interdependency.github.io`.

## Core contract

A website modification is incomplete until the builder expands **By the builder**.

For every change transaction that modifies any website-repository file other than the journal append itself:

1. append at least one new record to `src/_data/builder.json`;
2. preserve every previously published record byte-for-byte in value and order;
3. record the entry's **date**, **time**, and **exact runtime model**;
4. render the journal behind the site's collapsible `<details>` tree; and
5. pass the repository's builder-history gate before merge.

The journal append is part of the same transaction and does not recursively require a second append. Read-only inspection that changes no website file is the non-trigger.

## Entry contract

New records require:

```json
{
  "id": "<stable-fragment>",
  "date": "YYYY-MM-DD",
  "time": "HH:MM±HH:MM",
  "model": "<exact runtime model>",
  "body": "<builder-chosen subject>"
}
```

`id` is a stable technical anchor. Optional fields may support presentation or append-only correction links, but they must not create editorial requirements beyond this contract.

### Exact model

Write the full model identity actually executing the modification, not a provider, product, role, or generic agent label. Examples of insufficient values include `OpenAI`, `Codex`, `Claude`, `builder`, or `AI`.

If the runtime does not expose enough information to identify its exact model, the website modification remains blocked at `hmmm`; do not invent a model name.

### Subject and length

The model has complete discretion over the journal entry's subject matter. It does not have to summarize the patch, justify the modification, discuss the website, or follow a recurring theme.

Write only as much as is required to properly explicate the chosen subject. There is no minimum length, target length, mandatory title, changelog template, or required rhetorical shape.

## Append-only boundary

Previously published entries are immutable.

- Corrections are new entries; never rewrite the earlier entry.
- Deletion, replacement, or reordering of prior entries fails the gate.
- Historical records that predate the date/time/model contract remain unchanged. Do not backfill them, because doing so would violate the stronger append-only rule.
- New entries must satisfy the current entry contract.

## Collapsible-tree boundary

`/by-the-builder/` is a static-first collapsible tree implemented with semantic `<details>` / `<summary>` elements. JavaScript may enhance it but must not be required to read the entries.

The tree presentation may evolve. The requirements that survive presentation changes are: the journal remains collapsible, every entry remains reachable, and its date, time, and exact model remain visible.

## Workflow

1. Resolve the exact website base commit before editing.
2. Make the authorized website modification.
3. Before terminal validation, append one or more compliant builder records.
4. Run:
   ```bash
   npm run check:builder -- --base <base-commit>
   ```
5. Run the website's normal release gate.
6. Merge only if the builder-history contract and the website's other required checks pass.

The builder-history checker is enforcement; this skill is the behavior contract. Neither substitutes for the other.

## Validation

A conforming implementation proves all of the following:

- a non-journal website diff with zero appended entries fails;
- a non-journal website diff with at least one valid appended entry may proceed;
- a journal-only append does not trigger infinite self-requirement;
- prior entries cannot be edited, deleted, or reordered;
- every newly appended entry has non-empty `date`, `time`, `model`, and `body`;
- the time includes an explicit UTC offset;
- generic provider/agent labels are not accepted as substitutes for the exact model by doctrine;
- the public route renders the entries inside a collapsible semantic tree;
- the gate runs in the website's normal validation path.

## Anti-patterns

- Treating the journal as an optional changelog.
- Appending one entry once and letting later website changes reuse it.
- Rewriting an old entry to add the newly required model or time.
- Forcing the entry to describe the patch.
- Padding an entry to satisfy an invented word count.
- Recording only the provider or agent product instead of the exact model.
- Requiring another append because the current transaction appended to the journal.

## Usage guidance

When this skill is installed in the website repository, load it before the first write. The smallest compliant transaction is:

```text
website change
+ one new builder record {date, time, exact model, body}
+ check:builder
+ normal website release gate
```

## hmmm

The first published builder entry predates the date/time/exact-model contract. It remains intentionally unchanged because append-only history outranks retroactive schema neatness.
