# Behavior and effects: the executable approach

This is the method implemented by `capcov behavior`. See the
[unified system](unified-behavior-system.md) for commands and implementation status,
and the [publication example](../examples/behavior-publication/README.md) for a
runnable vertical slice. Application inventories and production evidence belong
in the consuming repository.

## Unit of work

A **Behavior** links an entry point, a target handler and its workers to recovered
legacy behavior, state access contracts, decisions and qualification obligations.
Entry points include routes, consumers, scheduled commands, callbacks, startup
and administrative programs. Functions are useful source anchors; they are not
necessarily the units of migration. Several routes sharing an invariant may need
to move as one cutover unit.

The recovered description is a relation:

```text
Legacy(baseline, state, event, environment) -> possible histories
```

It includes observable failures, partial commits and environmental choices. One
recording is evidence for one history, not the complete relation. The target
handler is deterministic given its request, trusted context and the sequence of
effect results. Its live environment can still be concurrent or nondeterministic.
Selecting one legacy-permitted outcome needs a recorded decision when it changes
observable guarantees; selection must also preserve required progress.

Compare legacy to its recovered model, target to its intended contract, and the
two implementations through an explicit migration policy. Agreement can preserve
a shared bug. A difference can be an approved correction. Neither conclusion
follows from response equality alone.

## Four store layers and the access-path matrix

| Layer | Record | Example |
| --- | --- | --- |
| Physical | Schema, keys, defaults, constraints, tenant placement, isolation | Tenant plus issue ID is a composite key |
| Representation | Physical-to-logical meaning, sentinel domains, codec laws | `N/A` means an unassigned identifier |
| Access | Reads, scopes, hooks, lazy loads, transactions, bypasses | ORM save runs an observer; direct SQL does not |
| Domain | Invariants and permitted transitions | Publication atomically records durable notification intent |

**Hooks and scopes belong to access paths, not automatically to the database.**
An Eloquent observer does not run when another application executes raw SQL.
Database triggers do. The matrix records each writer/reader, its actual mechanism,
hooks, scopes, bypasses and supporting artifacts. Every writer sharing a selected
store enters the qualification scope, even if the target handler never calls it.

A pinned schema snapshot is a reasonable starting assumption. Pin its tenant
variants and migration identity too. Data values, cache state and mixed writers
continue changing. Sample overloaded value domains and preserve unknown values
as representation gaps. Codecs can decouple logical values from storage encoding;
they cannot by themselves migrate constraints, IDs, relationships, transaction
boundaries or concurrent writers. Lossy decoding needs an explicit decision.

## Target execution

The executable fragment is deliberately small. `capcov-step-program-v1` declares
phase, an operation effect row, operation input/result fields, named nodes and an
entry node. Shen admits the program and interprets its steps. The Python host
serializes data, correlates results and runs adapters; it does not choose the
handler's transitions.

| Step | Meaning | Permitted phase |
| --- | --- | --- |
| `Ask` | Read or obtain an environmental value, with explicit alternatives | Route or worker |
| `Commit` | Request a durable local state transition, including outbox intent | Route or worker |
| `External` | Attempt externally visible delivery | Worker only |
| `Done` / `Failed` | Produce a terminal observation | Route or worker |

An operation label is a contract, not physical enforcement: an adapter that sends
mail inside `Commit` violates the contract. Test adapters independently. A remote
read may be an `Ask`; its response remains an explicit input. Time, random values,
flags and credentials must enter through reviewed context or effect boundaries.
Capture changing flags at their actual observation points if legacy does so.

`behavior-step.shen` defines sequent judgments for phase permissions and closed
program admission. Admission checks operation-row membership, input fields,
exhaustive tagged outcomes and named continuation closure, including unreachable
nodes. A route cannot declare an `External` capability in its row. Its pure
expression fragment currently consists of string literals and environment
references. Domain arithmetic, codecs, invariants and termination are separate
obligations; this is not a full effect-polymorphic source language.

The kernel is installed under `tc -` like the existing semantic kernels. Admission
explicitly calls `shen.typecheck` against the object-language datatype. That is a
checked judgment in a trusted rule environment; it is not a proof that every
checker helper or adapter is correct. Existing capcov contract proofs remain a
separate mechanism. Do not call an admission receipt a domain proof.

Wire messages contain values and workflow/sequence/program correlation. They do
not carry executable closures or grant type authority. The host owns the program,
phase, context and cursor; result values cannot overwrite request/context fields.
A mismatched, duplicate or out-of-sequence response is rejected. Checkpoints are
trusted host data and must be durably stored and authenticated by the application.
Restoring a pending effect requires reconciliation; it never automatically sends
that effect again.

## Recovery and evidence

Combine source/configuration extraction, runtime traces, store observation and
human interpretation. Reuse capcov's AST/SCIP discovery and source-anchor machinery.
The new registry references those artifacts; it does not replace their parsers.
An ORM call graph may miss dynamic wiring. A trace may miss an unexercised hook.
Explicit gaps preserve both limits.

Recovery imports use `capcov-recovery-v1`: source-linked claims, confidence labels
and gaps. Both `confirmed` and `inferred` agent extractions remain **static**.
Agreement between agents is review evidence, never execution evidence. Recovery
claims do not discharge obligations merely by declaring a confidence label.

Obligations state a category and required method: static, execution, proof,
model-check or review. Reviewed check plans map executable commands to those
obligations. The runner records fresh executions, input hashes, scope hashes and
bounded logs. Gate evaluation rechecks these bindings without executing commands.
A failed required check cannot be hidden by a second passing check. Hashes detect
drift, not fraudulent producers: check definitions, observers and receipt storage
remain in the consumer's trusted computing base.

## Comparison and protocol checks

Use three complementary validation modes:

1. **Recorded effect replay.** Match kind, operation, payload and order before
   supplying a recorded response. Compare terminal output too. This checks handler
   orchestration without dispatching external effects.
2. **Stateful execution.** Run legacy and target against controlled equivalent
   state, compare responses, ordered effects and state projections. Include
   sequences, partial failure, invalid inputs, representation laws, authorization
   changes and mixed writers. Mocked reads alone cannot validate new SQL.
3. **Protocol exploration.** Use TLA+ for commit/outbox separation, ownership,
   retries, duplicate delivery and interleavings. Record finite bounds and provider
   assumptions. A TLC result checks its model, not the adapter-to-model mapping.

Normalize only reviewed differences. Preserve entity relationships when mapping
IDs; do not erase ordering, timestamps or duplicates that users observe. The
implemented comparator grants changes only for an exact behavior, scenario,
JSON path and old/new pair with approved replacement obligations. Missing fields
are distinct from null. Broader normalization requires a separately tested codec.

The example demonstrates the outbox boundary and provider deduplication. Its
protocol obligation runs the pinned ShenCheck/Vör effects lane automatically:
Vör exports the authoritative model, ShenCheck generates TLA+, and reference/TLC
agreement plus all four defect controls are mandatory. There is no separately
maintained capcov protocol model. A fresh observer checks the concrete request
commit/response prefix against that model. Worker refinement, fairness and
liveness remain open; finite acceptance does not establish exactly-once delivery.

## Vertical delivery and release policy

Do a shallow inventory across all applications first: entry registry, access
matrix, effect vocabulary and available recordings. Then complete one important
cutover unit through recovery, implementation, replay, store tests and protocol
checks. Expand to independent units after the method works on executable code.
Prioritize behavior that users rely on; dead or shadowed routes need an explicit
classification. Priority schedules work and never waives safety.

The implemented cutover-policy gate requires declared obligations in authorization,
tenant isolation, representation, durable effects, coexistence, recovery,
compatibility and target contract. Open gaps, ambiguous representations, unapproved
decisions, stale inputs or missing evidence block it. This is a gate over reviewed
checks, not deployment approval or a universal equivalence theorem. Consumers
must justify that the checks cover each actual route, context and failure mode;
the CLI does not infer production traffic coverage from a green test suite.
