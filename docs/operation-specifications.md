# Typed operation specifications: delete-issue milestone

For the compositional system engine, use [System specifications](system-specifications.md).
This page documents the compatible original single-operation API.

This experimental path defines an operation once, checks its construction with
Shen's sequent datatypes, and uses a pure Shen effect interpreter to derive its
state transition, ordered effects, outcome alternatives, trace and static access
summary. Shen Prolog checks observations and searches a finite supplied state
set for a disagreement between variants. Python only parses/transports data,
launches Shen, and records source/request/runtime/library identities.

## Run it

Use the existing pinned Shen shell:

```sh
nix develop .#shen
PYTHONPATH=src python -m capcov.operations \
  --spec tests/claim_semantics/fixtures/operations/delete-issue.op \
  --request tests/claim_semantics/fixtures/operations/request.json
```

The package also runs from an installed wheel. Its Shen kernel and datatypes
are package resources; only the caller's specification and request are needed.
`bifrost` and `BIFROST_SHEN_GO` must name the configured native runtime. There is
no Python evaluator fallback. CLI exit codes: 0 completed with no rejected
observation/trace, 1 observed behavior or trace rejected, 2 invalid input or
operational failure. `--out` writes JSON; `--timeout` bounds native execution.

## One specification

The synthetic application model lives in tests, not the reusable engine:

```text
[operation "delete-issue" [live "issue" "state" "active"]
  [[named "cascade-comments" [delete-related "comment" "issue_id"]]
   [named "cascade-files" [delete-related "file" "issue_id"]]
   [named "mark-deleted" [set-target "issue" "state" "deleted"]]
   [named "statistics" [emit-related "issue_equipment" "issue_id" "equipment_id" "stats-recompute"]]
   [named "audit" [emit-target "audit:issue-deleted"]]]]
```

The `.op` file is restricted bracketed data. It cannot define functions, load
files, call a host, or inject Shen forms. Instructions are checked as inhabitants
of `capop-action`; named instructions compose into `capop-actions` and finally
`capop-program`. Duplicate action identities and programs above 64 instructions
are refused. The public native execution path uses these same datatype judgments
for construction admission; it does not maintain a second procedural instruction
validator. This establishes construction validity, not arbitrary application
invariants or correctness of the Shen implementation.

Each instruction produces an ordered effect list. `capop.apply` is the only
place those effects modify state. There are no independent handwritten `step`,
`effects`, `successor`, and `writes` implementations of delete-issue.

| Instruction | Meaning |
| --- | --- |
| `delete-related T F` | Delete rows in table T whose field F equals the target key |
| `set-target T F V` | Set field F on the existing target row in T |
| `emit-related T F K E` | Emit intent E for each matching row's field K |
| `emit-target E` | Emit intent E with the target key |

Every instruction reads the current intermediate state, after earlier effects.
A missing target for `set-target` or a missing selected event key is an explicit
operational failure. No partial result is returned. Rows have unique
(table, key) identities and unique string fields. Keys are globally unique
within their table; this model does not implement tenant-relative keys or
authorization rules. Other targets are preserved by the supplied delete model.

## Inputs and variants

Requests contain `state` (an array of `{table,key,fields}` rows), `target`, and
`outcome` (`committed`, `aborted`, or `unknown`). Optional `variant` is either
`"intended"` or an explicit named omission:

```json
{"divergence":"d-01: missing child cascade",
 "omit":["cascade-comments","cascade-files"]}
```

Unknown or duplicate omission names and empty divergence IDs are rejected.
Omissions cannot add arbitrary effects. Variants are different models, not
waivers: deployed behavior is rejected against the intended model. The variant
is bound into the request digest. Selecting a divergence does not constitute
reviewer admission of that divergence into any production evidence policy.

State row order is significant: it determines iteration and effect order. Field
names are canonicalized. A real database adapter must supply stable row order;
this milestone does not infer SQL row ordering. The legacy `model_min` fixture
and its frozen hashes remain unchanged. Its domain-specific `norn.*` ABI is not
silently replaced by this normalized row representation.

## Outcomes and checking

The model describes **atomic commitment of state changes and effect intents**:

- Committed on a live target admits the computed successor and full intent list.
- Committed on a missing/deleted target is refused and admits no result.
- Aborted admits exactly the pre-state with no effects.
- Unknown on a live target retains pre-state/no-effects and committed successor.
- Unknown on a nonlive target retains only pre-state/no-effects.

`emit` is an intent, such as an outbox entry; it does not send an external event.
These alternatives do not model partial delivery or crashes between external
side effects. Such systems need an explicit non-atomic operation semantics;
this result cannot establish their atomicity.

`transition` is the prospective committed result, or `[refused, nonlive]`.
`admissible` applies the requested outcome. In particular, `transition` is not an
assertion that an aborted request committed. Optional `observed: {state,effects}`
is checked by Prolog membership in the finite alternatives. Extra effects,
wrong order, residual children under the intended model, and incorrect state
are rejected. A false observation check is a model disagreement, not a runtime
error. A timeout never becomes semantic refutation.

An optional `trace: {state,effects,steps}` supplies steps of the form
`{name,effects}`. The checker reconstructs the execution under the supplied
specification, variant, pre-state and target; changing an action name, an effect,
or the result rejects the trace. This is a recomputed trace, not a separate
small proof kernel. Results bind the specification bytes, canonical request,
Shen binary, launcher, and every semantic library by SHA-256. Typechecking,
trace checking and external-world completeness are distinct claims.

Optional `search: {variant,states}` asks Shen Prolog for the first state in the
supplied finite domain where the two variants differ in state/effects (trace
labels alone do not count). It returns a `counterexample` or false. An empty
domain or no witness is **not** a proof of equivalence. It does not generate
states automatically or silently assume a complete domain.

## Analysis and completeness boundary

`analysis` reports reads, **may-write** tables and **may-emit** intent kinds.
For the intended delete, may-write is comment/file/issue even when there are no
children in the input. The deployed variant may-write is issue only. Observed
writes on example states do not turn that upper bound into exhaustive coverage.

No operation result creates a capcov completeness fact, policy admission, or
`model_operation_checked` fact. Connecting this model to replay receipts needs
an explicit reviewed adapter binding state abstraction, effect interpretation,
model identity, operation identity, and observation scope. In particular, the
existing v2 named-closure-policy trust boundary is not strengthened by merely
running this model: a rule digest binds identity, not a proof of closure.

## Bounds and validation

Limits: 1 MiB specification/request, nesting 16, 4096 UTF-8 bytes per string,
256 rows per state, 64 fields per row, 64 instructions, and 16 candidate search
states. No loops, callbacks, host clock, entropy or I/O exist in the instruction
language. A subprocess timeout bounds the host execution. Large valid programs
may still exhaust that timeout; resource failure is distinct from rejection.

`tests/claim_semantics/fixtures/operations/cases.json` contains independently
written expected outcomes, not generated snapshots from the implementation.
Native tests cover intended/deployed behavior, outcomes, wrong/extra/reordered
effects, type failures, trace mutations, may-write versus observed writes,
Prolog discrepancy search and Unicode transport. Tests are assigned to the Shen
CI family; missing Shen is an error when `CAPCOV_SHEN_REQUIRED=1`.

```sh
PYTHONPATH=src python -m unittest tests.claim_semantics.test_operations -v
```

The remaining work is general invariant judgments, richer transitions and
non-atomic effects, automatic bounded scenario generation, independent proof
checking, and a production model/receipt adapter. V1 and replay-v2 defaults and
existing completeness contracts are unchanged by this milestone.
