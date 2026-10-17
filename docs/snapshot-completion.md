# Proving that snapshot transformations complete

The loop compiler now supports a `completes` predicate alongside an invariant:

```json
{
  "close-all": {
    "items": {
      "invariant": "[every-row \"item\" [either [equal [row-field \"status\"] [literal \"open\"]] [equal [row-field \"status\"] [literal \"closed\"]]]]",
      "completes": "[equal [row-field \"status\"] [literal \"closed\"]]"
    }
  }
}
```

`invariant` describes state between iterations. `completes` describes one row of
the iterated table. A successful completion proof establishes `every-row` of
that predicate at loop exit, as well as the invariant. The usual continuation
obligation then connects those results to the rest of the command.

```sh
capcov reason loops \
  --spec tests/claim_semantics/fixtures/systems/loop-completion.ops \
  --input tests/claim_semantics/fixtures/systems/loop-completion.json \
  --out completion-proof.json
capcov reason check-loops \
  --spec tests/claim_semantics/fixtures/systems/loop-completion.ops \
  --input completion-proof.json
```

The same contracts work through `loop_invariants` in the verification pipeline.
String-valued invariant annotations remain supported.

## Partition induction

Let P be the selector and Q the completion predicate. The captured selection
is a list of rows with distinct keys, guaranteed by the model's state validity
judgment. The proof uses these ghost relations; it does not add mutable ghost
state to application execution:

* Selected = Processed ++ Remaining.
* Processed and Remaining contain distinct, disjoint keys.
* Every processed row satisfies Q in live storage.
* Every remaining row still has its captured fields in live storage.
* Every row outside Selected satisfies Q, and the table's key set is unchanged.

Initially Processed is empty. The command must establish the invariant and
`every-row (P or Q)` at loop entry: this supplies Q for the unselected rows.
For selector `yes`, this coverage requirement is trivially true. The compiler
pushes coverage backward through preceding actions rather than assuming it.

For the next captured row, its captured selector P is true. Its current fields
match its snapshot because earlier iterations could only update their own,
different keys. The compiler derives the weakest precondition of the body for
Q, then uses this head-row equality to replace entry-state reads of that row
with its immutable captured fields. A Shen-checked sequent proves that captured
P implies this precondition.

After the body, Q holds for the head. The mutation frame preserves Q for previously
processed and unselected rows and preserves the snapshots of remaining rows.
Moving the head from Remaining to Processed preserves the partition invariant.
When Remaining is empty, every live row satisfies Q. This is a finite-list
induction, independent of the number of rows explored by tests.

A selector may become false during processing. For example, selecting `open`
rows and closing them is supported: selection was captured once, and the proof
uses captured P, not a claim that P is still true in live storage. Initially
unselected rows need coverage; an empty selection cannot prove that arbitrary
rows were transformed.

## Enforced frame and supported language

The completion rule admits `update` only on the iterated table with the exact
key expression `row-key`. `choose` recursively enforces that restriction on both
branches. `require` and `publish` are supported because they do not mutate model
storage. Shen independently rechecks this frame against the original body.

Cross-key writes, cross-table writes, insertion, deletion and nested loops inside
a completion body remain open. They need stronger frame/domain proofs. Existing
invariant-only nested-loop support is unchanged.

P and Q must be row-local predicates: Boolean combinations, row key/fields,
command arguments, literals, integer arithmetic and comparisons. Global state
lookups and quantified predicates in P or Q need a stronger partition rule and
remain open. The body may read storage, but the step proof must justify those
reads; only entry reads of the head row receive snapshot substitution. `before`
values never receive that substitution.

Restoring a captured value after an update does not count as completing the
update. Missing work, a conditional branch that skips necessary work, and stale
restoration produce open completion obligations.

## Typed judgments and trust boundary

`completion-types.shen` defines genuine Shen sequent-calculus datatypes for
propositional formulas, contexts and the `snapshot-partition` judgment.
`cl.partition-typechecks?` calls Shen's typechecker before the completion rule is
accepted. This is datatype checking of the judgment, not a claim that the entire
checker implementation or the claims authority layer is statically typed.

`loop-check.shen` independently checks the local mutation frame and the supplied
preservation, completion and continuation derivations. `check_loops` regenerates
coverage, substitution, obligations and rule records from the executable source.
Deleting an obligation or forging a frame/coverage record fails even if an
attacker recomputes the artifact digest.

The Python weakest-precondition, snapshot-substitution and obligation-generation
code remains trusted and content-identified. The partition rule's semantic
connection to the interpreter is not itself a mechanized interpreter-refinement
proof. Artifacts bind both the new transformation and datatype hashes.

These are partial-correctness results for successful executions. They do not
prove expression totality, adequate fuel, nonvacuous reachability, delivery of
external effects, or source-to-model equivalence. Native runtime and input bounds
remain unchanged. The generalized quantified datatype/relational proof language
is still further work.
