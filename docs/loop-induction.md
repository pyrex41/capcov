# Induction for executable snapshot loops

`capcov reason loops` proves partial correctness of annotated commands in an
existing `.ops` system. Its loop rule applies to arbitrary finite snapshot
lengths. It does not enumerate row counts or infer correctness from successful
runtime postcondition checks.

```sh
capcov reason loops \
  --spec tests/claim_semantics/fixtures/systems/loop-induction.ops \
  --input tests/claim_semantics/fixtures/systems/loop-invariants.json \
  --out loop-proof.json
capcov reason check-loops \
  --spec tests/claim_semantics/fixtures/systems/loop-induction.ops \
  --input loop-proof.json
```

Exit codes follow the workbench: zero for proved/verified, one for an open or
unverified result, two for invalid inputs or operational failure.

## Contracts and obligations

Annotations are a JSON mapping from command name to named loop to invariant,
written in the existing predicate syntax:

```json
{
  "close-all": {
    "items": "[every-row \"item\" [either [equal [row-field \"status\"] [literal \"open\"]] [equal [row-field \"status\"] [literal \"closed\"]]]]"
  }
}
```

The model fixture updates each captured item's status to `closed`. Its global
invariant permits `open` or `closed`. The original compiler cannot substitute a
mutation keyed by a loop row and leaves preservation open. The annotation lets
the new compiler prove preservation for every iteration and compose the result
with command entry and continuation obligations.

Each invariant is checked using Shen's `caps-pred` datatype and the actual model's
scope rules. It may refer to command arguments, declared tables and fields,
quantified rows, and `before` values from command entry. Free `row-key` and
`row-field` references are forbidden: the invariant describes state between
iterations, not a particular current row. Unknown commands/loop names fail.

The compiler produces:

| Obligation | Meaning |
| --- | --- |
| Initiation | The command precondition and initial global invariants establish the weakest precondition of its actions, including each reached loop invariant. |
| Preservation | A loop invariant establishes the body's weakest precondition for that same invariant, for an arbitrary captured row. |
| Continuation | The invariant implies what is required after the loop, including the empty-snapshot case. |

Every command postcondition and global invariant gets an initiation obligation.
Preservation obligations are shared between those goals. Nested loops use the
same rule recursively; the enclosing body's weakest precondition must establish
the nested invariant. `choose` carries branch conditions through the existing
weakest-precondition transformation. `require` retains partial-correctness
semantics: a rejected transaction is not a successful path.

At intermediate states, the checker does not assume the command precondition or
all global invariants still hold. Needed facts must be carried by the loop
invariant. Sound guarded instances of a universal invariant may be derived using
the existing compiler's universal-elimination rule.

## Snapshot semantics and binding

The executable Shen model first selects a list of rows, then passes each captured
row to the body. Modifying live storage does not modify those captured values.

The compiler replaces a loop's free row key and fields with fresh rigid
parameters. These parameters are distinct from command arguments and parameters
for other loops. Quantified predicates and nested loops introduce new row
bindings; substitution does not cross those bindings. Subsequent live updates
cannot rewrite captured values.

For example, setting a row's status to `closed`, then restoring its captured
status, can leave it `open`. The tests execute this case in Shen and ensure the
symbolic transformation preserves the original captured value.

This version deliberately proves body preservation for **any** captured row.
It does not assume the selector remains true against live storage, or even
assume captured fields equal current fields. This is conservative: some valid
loops remain open until snapshot membership and processed/remaining relations
are represented explicitly.

The induction measure is the remaining captured list, whose tail is passed to
the next `caps.each` call. Mutations of a table cannot enlarge that already
captured list. Nested loops take their own snapshots. This explains the finite
list induction rule; it does not establish expression totality, successful
execution, or a sufficient runtime fuel budget.

## Certificates and trust

`capcov-loop-induction-v1` binds the source hash, exact annotations, compiler
hashes, native runtime/system library identity, sequent proofs, and loop-rule
hash. The independent checker:

1. Regenerates obligations and rule composition from the supplied `.ops` source.
2. Rejects missing or substituted obligations and changed model/compiler/runtime
   identities, even when the envelope digest has been recomputed.
3. Checks each derivation using the existing Shen sequent kernel.
4. Checks the preservation/continuation composition using `loop-check.shen`.

The checker does not invoke proof search. The Python API can additionally bind
expected annotations:

```python
from capcov.operations.loops import prove_loops, check_loops

proof = prove_loops(source, invariants)
verified = check_loops(source, proof, invariants=invariants)
```

The weakest-precondition transformations, capture substitution and generated
universal instances remain trusted compiler code, identified by hash. This is
not yet a mechanized proof of the compiler against the Shen interpreter.
Arithmetic normalization and conservative alias analysis have the same scope as
the existing compiler. Search retains its formula/atom limits; an unsupported
transformation or oversized obligation stays open, never proved by omission.

An impossible invariant can make preservation vacuous but still fails initiation
unless the command is itself unreachable. As with other partial-correctness
proofs, reachability and successful completion require separate witnesses.

## Verification pipeline

Pass `loop_invariants` in the `capcov reason verify` input, or as a keyword to
`workbench.verify`. The pipeline generates and independently checks the loop
certificate before using it to discharge model obligations. It retains the
original compilation unchanged, records the full certificate as `loop_induction`,
and identifies those obligations in each claim's
`loop_proved_model_obligations` list. If any obligation in the supplied loop
certificate remains open, that certificate discharges no claims.

The proof applies to annotated commands in the executable model. Source anchors,
source freshness, runtime conformance and implementation refinement remain
separate evidence dimensions. A proved loop does not automatically authorize a
migration target or establish equivalence to a production service.

## Further induction work

The [snapshot completion rule](snapshot-completion.md) now uses processed and
remaining rows to establish completed transformations for row-local updates with
a checked mutation frame. Cross-key/domain-changing transformations, generalized
quantified datatype induction and checked compiler refinement remain further
work. Existing unannotated loops retain their frame/deletion rules or stay open.
