# Typed claim authority (W2, first increment)

`shen.typed_authority(bundle)` (request `[capcov.typed-authority]`) is a third
authority over the elaborated claim IR, next to Python validation
(`claims/validation.py`, `claims/authority.py`) and the untyped Shen
authority (`shen/rule-authority.shen`, `shen/evidence-authority-v2.shen`). It
reports the untyped authority's check ids, in the same order. Each verdict
is a typing judgement checked by Shen's type checker. It does not reuse the
untyped verdicts.

## How a verdict is produced

1. `shen/typed-authority.shen` reifies each elaborated rule as the typed IR
   in `shen/claim-types/telescope.shen`. That IR has typed terms
   (`[cc.uvar X]` or `[cc.const V Tag]`), premise occurrences
   `[cc.occ I Item]` that keep their source position, and relation
   references with their declarations resolved
   (`[cc.rel Name Decl Class Component]`). Unification variables get their
   sorts from `cc-sort` hypotheses. A variable counts as bound only through
   a `cc-bound` hypothesis, and only `cc-bind` introduces those, for
   positive premises. Source names never become hypotheses.
2. A unit is `(shen.typecheck <IR syntax> [cc-judged Sort])`, run after
   `(tc +)`. If the checker derives the type, the check passes. A failed
   derivation, a raised error or an exhausted per-unit inference budget
   (10^6) fails the check. Every (rule, check id) pair is its own unit.
3. Under schema 2, `context-index-loss`, `unsupported-context-widening` and
   `negative-conclusion-without-completeness` also require the pack-level
   `cc-contracts` judgement (basis `typed+contracts`). This matches
   `capcov.v2-check`.

Each check in the output carries a `basis`: `typed`, `typed+contracts`,
`trusted-elaborator` or `unsupported`.

## Semantic rules checked by typing

| Check id | Sort (file) | Rule enforced by the derivation |
| --- | --- | --- |
| `typed-rule` (v2) | `cc-typed`, `cc-conforms` | Every atom has exact arity. Each variable sits only at columns of its one sort. Each constant is a literal of its column type. |
| `undeclared-relation` | `cc-declared` | Every atom's reference resolves to a declaration. |
| `ungrounded-conclusion-variable` | `cc-conclusion`, `cc-bind` | Head variables are `cc-bound` by some positive premise. |
| `ungrounded-side-condition-variable` | `cc-side`, `cc-bind` | Negation and comparison variables are bound by a **preceding** positive premise. |
| `context-index-loss` | `cc-head` (v2), `cc-legacy-head` (v1) | Each head context index is carried from a positive carrier, or by an authorized or bridged join, or is an unconflicted constant. |
| `unsupported-context-widening` | `cc-widening`, `cc-authorized` (v2), `cc-legacy-widening` (v1) | Every pair of carrier occurrences agrees on each shared index or has an authorized join. Applicable bridges are authorized. |
| `negative-conclusion-without-completeness` | `cc-complete`, `cc-closes` | Each declared negation has an exact scoped closure occurrence (v2: all mapped columns `cc-same`; v1: identical shared terms). Negated witnesses are never closed. |
| `declaration-promoted-to-effect` | `cc-promotion` | A runtime conclusion needs effective support, an assumption projection, or scoped absence. |
| `non-linear-recursion` | `cc-linear` | A rule has at most one premise in the head's recursive component (one affine token). |
| `evidence-contracts` (pack, v2) | `cc-contracts` | Scopes, capabilities and bridges are well formed, legacy metadata is refused, names are unique, and policies bind exact digests. |

Classification (`cc-classify`) is derived. Its guards are mutually
exclusive, so the reifier cannot hide a carrier by calling it inert. A
completeness premise carries its target's positions only through the
explicit scope mapping. Authorization (`cc-authorized`) names the two
carriers and their dimensions, and no rule composes authorizations. This is
what makes compatibility non-transitive and keeps premise occurrences
distinct.

## Remaining untyped or trusted

The following parts are **not** checked by the type checker:

* **Prelude predicates** (`shen/claim-types/prelude.shen`): `cc.eq?`,
  `cc.member?`, `cc.length-differs?`, `cc.literal-ok?`/`cc.admits?`,
  `cc.bridge-applies?`, `cc.unique?`, `cc.same-sorted?`, `cc.subset?`,
  `cc.names-arg?`, `cc.runtime-effect?` and the field projections. These
  are untyped Shen functions that side conditions call.
* **The reifier** (`shen/typed-authority.shen`). It copies declarations,
  scopes and contracts into references, and it proposes variable sorts.
  The sort proposals are refutable, but the copying is trusted.
* **Pack analyses taken from the workbench elaborator:** the
  assumption-projection closure (`Class`), the recursive-component analysis
  (`Component`), the stratification (`stratified-negation`) and the frozen
  checksum (`frozen-pack-mismatch`). The last two report basis
  `trusted-elaborator`.
* **The checker itself:** the runtime's sequent-calculus checker (shen-scheme
  by default, kernel 43.1; shen-go S42 gives the same verdicts) and the
  workbench parser and elaborator that produce the rule records.
* **Aggregation.** It has no sort, so a rule that uses it fails every check
  with basis `unsupported`.

Do not equate function typechecking with a proof of logical soundness.
These datatypes type the *syntax of the claim IR* under judgement rules that
mirror the existing authorities. A derivation shows that a rule satisfies
those rules. It does not show that the rules are sound for the evaluators,
that the reifier transcribed the pack faithfully, or that the prelude
predicates are correct. Function signatures (`{A --> B}`) are not used for
any judgement.

## Measured constraints (shen-go c12933d)

These were measured on shen-go. The default runtime is now shen-scheme v0.52
(kernel 43.1). Its typed batch decides the same 3148 units with the same
verdicts in about 14 s against about 355 s
([shen-runtime-choice](shen-runtime-choice.md)). The inference-count notes
below are kernel-level and were not re-measured separately.

* A goal costs inferences linear in the hypotheses in scope. Keeping one
  hypothesis per relation made pack-sized units quadratic, so declarations
  travel inside references. Only binding, sorts, capabilities and bridges
  are hypotheses.
* A side condition runs before the premises of its rule. Facts about a value
  that a premise produces are therefore stated as a later premise
  (`[cc.is X Y] : cc-test`).
* A hypothesis lookup needs a ground subject, so a search over alternatives
  walks explicit lists.
* An error that unwinds out of `shen.typecheck` makes every later unit in
  the process fail. For that reason every prelude predicate is total
  (`cc.total`).
* Shen's inference limit (`maxinferences`, default 10^6) counts from process
  start. The authority therefore resets it per unit to `(inferences)` plus
  the unit's budget.
* When a late conjunct of a conjunction of checks fails, the checker retries
  every combination of the alternative proofs of the earlier conjuncts. For
  a five-premise rule this took about 10^6 inferences, while its one failing
  check needed 6·10^3. For this reason each check is a separate unit, and
  guards (`cc.same-at?`) keep "same" and "authorized" from both deriving
  one join.
* Compiling the datatypes dominates start-up (tens of seconds of CPU).
  `bifrost run` kills the runtime after a fixed 60 s. Typed runs and batches
  therefore invoke the pinned binary directly, with the argv of bifrost's
  adapters (`{bin} script {file}`), under the Python-side deadline. On
  shen-scheme a typed batch takes seconds, but the direct path is kept for
  every runtime.
  `shen.authority_batch(..., typed=True)` judges many bundles in one
  process.

## Disagreements

`specs/claims/migration-preserved.json` → `typed_authority_disagreements`
records every case where the three authorities differ, with an analysis.
`tests/claim_semantics/test_typed_authority.py` asserts that this recorded
set is exact. No disagreement is resolved by adopting the more permissive
verdict.
