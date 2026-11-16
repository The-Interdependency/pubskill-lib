---
name: char-compress
description: Character-based context compression for agent handoff and skill writing. Use this when compressing a long thread, document, repo audit, canon handoff, or agent working-memory state; when a context window is filling and operative facts must survive; when writing a SKILL.md that should be flesh-dense and bone-sparse; or when checking whether a compression deleted negation, order, quantifier, operator, named object, value, decision, or unresolved hmmm. Historical bone/flesh terminology is local compression notation, not a theorem/status transfer.
---

# char-compress — bone/flesh compression for agent context

`char-compress` is a procedure: preserve irreducible content,
suppress only safely regenerable recurrence, and reconstruct through an
explicit shared grammar/domain. Its historical bone/flesh vocabulary is
retained as local compression notation. It is not an implemented compression
engine.

It separates text into:

- irreducible content that must be carried in full;
- meaning-critical small operators that must be frozen even though they look
  grammatical;
- regenerable connective scaffold that can be dropped and restored by grammar;
- unresolved boundary objects that must remain visible as `hmmm`.

The working asymmetry:

```text
Bones are often recoverable from inventory + grammar + slot expectation.
Flesh is not recoverable except by carrying the thing itself.
```

The compression rule:

```text
Drop only what is safely regenerable.
Carry every operative item exactly once.
When unsure, classify the unit as flesh.
```

## Channels

### FLESH channel

Open-class or content-bearing units carried in full.

Examples:

```text
entities, values, named objects, filenames, repo names, URLs, decisions,
claims, constraints, promises, statuses, dates, quantities, secrets,
private-key material, carrier choices, canonical spellings, unresolved hmmm
```

Flesh is expensive and irreducible. It is not inventory-determined. A value or
named object dropped as connective prose is unrecoverable.

### FROZEN_BONE channel

Closed-class, operator-like, or short structural units that look cheap but are
not safely regenerable because they control meaning.

Examples:

```text
not, never, no, without, only, all, none, some, any, if, unless, except,
before, after, during, until, must, may, should, cannot, first, second, last,
minus, plus, equals, not-equals, greater-than, less-than, public, private,
secret, experimental, defended, implemented, test-backed
```

Frozen bones are carried explicitly. They are bone-shaped but flesh-critical.
Dropping them creates the exact failures this skill exists to prevent.

### REGENERABLE_BONE channel

Closed-class connective scaffold that grammar can usually restore.

Examples:

```text
articles, routine prepositions, ordinary conjunctions, filler connective
phrases, repeated explanatory scaffolding, prose padding around already-carried
facts
```

Regenerable bones are the compression target. They may be dropped in
context-compression mode or carried as fingerprints in structure-preserving
mode.

### TRANSFORM channel

Affixes and grammatical surface changes stored as root plus transform.

Examples:

```text
root=compress, transform=-ion
root=measure, transform=-ment
root=run, transform=-ning
root=build, transform=re-
root=valid, transform=in-
```

The root is flesh. The transform is cheap if the domain grammar is shared.
When a transform changes legal, safety, or theorem status, treat it as frozen.

### HMMM channel

Visible unresolved constraints.

Examples:

```text
unknown source, missing bridge, unverified claim, incomplete test, ambiguous
bone/flesh boundary, security uncertainty, domain grammar mismatch
```

`hmmm` is not deleted. It is carried as an operative object.

## Suppression sort

Second-instance suppression on a string keeps the first occurrence of each
character and drops repeats:

```text
banana -> ban
committee -> comite
```

The result is an inventory fingerprint. In this local notation it preserves the
first-occurrence inventory, with recurrence retained as explicit ordered data
when required. For closed-class words in known slots, that fingerprint plus
grammar often recovers the word. For open-class content, the same operation can
destroy needed information unless recurrence and position data are carried.

Use suppression as a classifier, not as the complete codec:

```text
survives suppression + grammar can restore it -> candidate bone
breaks under suppression or carries operative fact -> flesh
looks grammatical but controls polarity/order/scope/status -> frozen bone
separator/boundary data that changes attachment or closure must be preserved
```

## Compression procedure

1. **Mark the domain.** State the repo, thread, language, and grammar assumed by
   the reconstruction. Compression is only lossless relative to that grammar.

2. **Declare the text grouping.** Use source-appropriate character, word,
   sentence, or other boundaries.

3. **Run a suppression sort.** Identify first-occurrence inventory,
   recurrence data required for reconstruction, units that survive as
   recognizable scaffold, and units that become ambiguous or lose operative
   force.

4. **Extract flesh once.** Record every distinct operative item in resolved form.
   Do not repeat a flesh item unless the repetition itself is meaningful.

5. **Freeze dangerous bones.** Preserve negation, quantifiers, conditionals,
   modal force, operators, ordering, proof/status labels, privacy labels, and
   any small word that controls meaning.

6. **Record transforms.** Store root plus transform where the surface form is
   regenerable. Promote the transform to frozen bone when it changes status,
   safety, legality, or theorem scope.

7. **Preserve boundary data where it changes attachment.** Spaces, punctuation,
   paragraph breaks, and other separators must survive when they affect
   attachment or closure.

8. **Drop regenerable scaffold.** Remove articles, routine connective prose,
   and repeated explanation that adds no new operative item.

9. **Carry hmmm.** Preserve unresolved constraints as explicit `hmmm` entries.
   Never convert unknowns into guesses to improve compression.

10. **Reconstruct and compare.** Regenerate readable prose around the skeleton.
    Check named objects, values, decisions, negations, operators, order,
    statuses, boundary/attachment closure, and hmmm. If any operative item is
    missing or inverted, move it to flesh, frozen bone, or preserved boundary
    data.

## Output shape for compressed handoffs

Use this notation-neutral shape when compressing a thread or repo audit.

```yaml
char_compress:
  domain: <repo/thread/document/language>
  mode: context-compression | structure-preserving
  flesh:
    - <distinct operative item>
  frozen_bones:
    - <meaning-critical operator/scope/status unit>
  boundary_data:
    - <space/punctuation/break/closure data that changes attachment>
  recurrence:
    - unit: <first-occurrence unit>
      positions_or_weights: <required recurrence data>
  transforms:
    - root: <root>
      transform: <prefix/suffix/class/aspect/polarity>
      status: regenerable | frozen
  dropped_bones:
    - <class of scaffold dropped, not every occurrence>
  reconstruction_checks:
    named_objects: pass | fail
    values: pass | fail
    decisions: pass | fail
    negation: pass | fail
    quantifiers: pass | fail
    order: pass | fail
    operators: pass | fail
    statuses: pass | fail
    boundary_closure: pass | fail
    hmmm: pass | fail
  hmmm:
    - <unresolved constraint>
```

## Skill-writing use

A `SKILL.md` should be flesh-dense and bone-sparse.

Keep:

```text
schemas, constants, invariants, load triggers, procedures, forbidden phrases,
status labels, tests, boundary rules, output shapes, hmmm
```

Minimize:

```text
long connective explanation, repeated motivation, prose restatement of tables,
examples that add no new boundary, decorative summaries
```

Do not remove:

```text
negation, ordering, scope, proof boundary, security warning, privacy status,
operator semantics, failure criteria, attachment/closure boundaries
```

Test a skill by stripping the connective prose. If the operative content still
stands, the skill is dense. If the rule changes when prose is removed, the
removed prose was misclassified.

## Executable support

Minimum preservation fixtures live in:

```text
.agents/skills/char-compress/fixtures.json
```

Run them with:

```bash
python .agents/skills/char-compress/char_compress_check.py
python .agents/skills/char-compress/char_compress_check.py --json
```

The runner is a local preservation guardrail, not a compression
engine. It verifies that the fixture skeleton preserves negation, quantifier,
order, values, statuses, secrets, `hmmm`, and the theorem/status boundary.

## Falsifiability tests

A char-compression fails if reconstruction produces any of these:

- missing named object;
- missing number, date, path, carrier, repo, or URL;
- dropped negation;
- widened `only`, `must`, `cannot`, `unless`, or `except`;
- swapped order of operations;
- changed proof/status label;
- transformed `private` into `public` or `secret` into `publishable`;
- replaced a specific class with a vague category;
- preserved decorative wording while deleting operative force;
- omitted an unresolved `hmmm`;
- treated a space, punctuation mark, or paragraph break as absence when it
  changes closure or attachment;
- lost recurrence order where ordered recurrence is required for reconstruction.

Minimum fixture set for an implementation:

```text
1. negation_preserved: "not a supervisor" does not reconstruct as supervisor
2. quantifier_preserved: "only X" does not reconstruct as "X among others"
3. order_preserved: first/then/last stays ordered
4. value_preserved: numbers, dates, paths, repos, URLs survive exactly
5. status_preserved: EXPERIMENTAL does not reconstruct as DEFENDED
6. secret_preserved: private carrier material stays private
7. hmmm_preserved: unresolved constraints remain visible
8. no_theorem_transfer: output does not claim unearned theorem/status support
9. boundary_preserved: spaces/punctuation/breaks that change attachment survive
10. recurrence_preserved: repeated units keep required position/order/weight data
```

## Security note

Compression is not opacity. Bone fingerprints leak structure: clause count,
hinge placement, relation shape, boundary placement, and sometimes operator
class. If opacity is required, the inventory-to-position mapping is key material
and must not be published.

Do not place private carrier arrangements, slot maps, secret alphabets, or
cryptographic mappings in public skills, public README files, demos, tests, or
handoffs.

## Completion criteria

A compression is complete when:

```text
all flesh appears once in resolved form;
all frozen bones are explicit;
transforms are root + transform;
source grouping and grammar required for reconstruction are declared;
boundary/separator details that affect closure or attachment are preserved;
recurrence position/order/weight data required for reconstruction are preserved;
regenerable scaffold is absent or fingerprinted according to mode;
hmmm is visible;
reconstruction preserves named objects, values, decisions, negation,
quantifiers, order, operators, statuses, boundary closure, recurrence, and unresolved constraints;
no theorem/proof/status support is inferred from this procedure.
```

## Anti-patterns

- Carrying full connective prose and calling it compression.
- Dropping a named object, value, status, path, repo, URL, or decision.
- Dropping `not`, `only`, `unless`, `must`, `cannot`, `before`, or `after`.
- Treating a short token as safe because it is common.
- Treating a meaningful separator as absence when it changes attachment.
- Treating recurrence weight as enough when ordered recurrence is required.
- Treating the bone channel as opaque.
- Compressing an unresolved constraint into silence.
- Treating the fixture runner as a full compression engine.
- Claiming theorem/status support without an implementation and tests.

## hmmm

- the bone/flesh boundary is grammar-relative and domain-relative
- numerals are inventory-poor like bones but content-bearing like flesh
- transform vocabulary may be closed in one repo and open in another
- reconstruction assumes a shared grammar; a different agent grammar may
  regenerate different bones
- `char_compress_check.py` is deterministic fixture support, not a full codec
- whether repeated characters become weights only, ordered recurrence layers only,
  or both
- whether future structure-preserving mode should carry bone fingerprints,
  dependency slots, twist seams, recurrence layers, or all of them
- whether opacity should layer on top of this compression or replace the
  inventory boundary with a secret mapping