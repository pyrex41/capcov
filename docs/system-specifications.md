# Compositional Shen systems

For source evidence, static obligations, independently checked sequent proofs,
typed relational generators and stateful replay, see the
[reasoning workbench](reasoning-workbench.md). The commands below remain supported.

`capcov system` executes a complete **finite abstraction** of an application's
state and operations. The same specification supplies simulation, access
analysis, bounded workflow exploration, model comparison, observation checking,
and reproducible certificates consumed by capcov's claim evaluator.

The engine is application-independent. Application schemas, API operations,
state abstractions and adapters belong in the consuming repository. The three
models under `tests/claim_semantics/fixtures/systems` are synthetic regression
fixtures: workspace CRUD/authorization, an idempotent ledger, and an outbox
workflow. They are not implementations of a particular production service.

## Commands

Use `nix develop .#shen` (or the repository's pinned bifrost/shen-go binaries):

```sh
capcov system evaluate --spec model.ops --input requests.json
capcov system explore --spec model.ops --input campaign.json
capcov system compare --spec intended.ops --other deployed.ops --input requests.json
capcov system certify --spec model.ops --input requests.json --out certificate.json
capcov system recheck --spec model.ops --input certificate.json
capcov system claims --spec model.ops --input certificate.json
capcov system harness --spec model.ops --input requests.json --adapter ./application-adapter
```

`PYTHONPATH=src python -m capcov system ...` and
`python -m capcov.operations.system ...` provide the same interface. Installed
wheels contain the semantic libraries; a source checkout is unnecessary.
`--fuel` sets action fuel; `--timeout` bounds each native/adapter subprocess.

Exit code 2 means invalid input or operational failure, including resource
exhaustion. Evaluate/certify/harness return 1 for a rejected supplied observation
or trace; compare returns 1 for discrepancies; explore returns 1 for reached
postcondition/schema/global-invariant violations. Claims returns 1 unless all
requested cases have support and no refutation. Recheck verifies reproduction,
so a correctly reproduced certificate containing a disagreement returns 0.
A simulation with no observation does not establish conformance.

Runnable repository examples:

```sh
PYTHONPATH=src python -m capcov system evaluate \
  --spec tests/claim_semantics/fixtures/systems/ledger.ops \
  --input tests/claim_semantics/fixtures/systems/ledger-requests.json
PYTHONPATH=src python -m capcov system explore \
  --spec tests/claim_semantics/fixtures/systems/outbox.ops \
  --input tests/claim_semantics/fixtures/systems/outbox-campaign.json
```

## Language

```text
[system "name"
  [[table "entity" ["field" [column "amount" [int32]]]
      ["field"] [[foreign "field" "other-table"]]] ...]
  [[command "operation" ["arg" ...] Precondition
      [[named "action-id" Action] ...] Postcondition] ...]
  [["invariant-id" Predicate] ...]]
```

All values on the transport are strings. Columns are text (a plain field name,
or `[column F [text]]`), canonical decimal int32, or finite enums
(`[column F [enum ["open" "closed"]]]`). Integers have no leading zero, `+`,
whitespace or negative zero. Arithmetic and sums check signed 32-bit overflow.
There are no implicit numeric conversions, floating values, nulls or optional
fields. More complex application values need an explicit abstraction.

A table has an exact field set, zero or more individually unique fields, and
foreign keys referencing another table's row key. Rows have unique `(table,key)`
identities. Schema constraints and named global invariants hold at transaction
boundaries. Temporary intermediate violations can be repaired before commit.
Initial states violating a constraint are operational errors.

| Expression | Meaning |
| --- | --- |
| `[literal V]` | String constant |
| `[argument Name]` | Declared command argument |
| `[row-key]`, `[row-field F]` | Current quantified/iterated row |
| `[lookup T Key F]` | Field of an existing row |
| `[int-add X Y]`, `[int-sub X Y]` | Checked int32 arithmetic |
| `[count-rows T]`, `[sum-field T F]` | Bounded aggregates |
| `[before X]` | Evaluate against transaction pre-state; postconditions only |

Predicates: `[yes]`, `[no]`, `[equal X Y]`, `[less-than X Y]`, `[negate P]`,
`[both P Q]`, `[either P Q]`, `[exists T Key]`, `[some-row T P]`, and
`[every-row T P]`. Boolean conjunction/disjunction short circuit. Guard a lookup
with `exists` when absence is an expected business condition; a missing lookup
or unparseable numeric expression is an operational error, not a false predicate.

| Action | Meaning |
| --- | --- |
| `[insert T Key [[F Expr] ...]]` | Create one row with exactly its schema's fields |
| `[update T Key F Expr]` | Update an existing row |
| `[remove T Key]` | Delete an existing row |
| `[publish Kind Expr]` | Append an ordered effect intent |
| `[require Label Predicate]` | Reject the transaction with Label if false |
| `[choose Predicate ThenActions ElseActions]` | Conditional composition |
| `[for-each T Predicate Actions]` | Execute a body for each selected row |

Actions read the current intermediate state. Iteration selects a snapshot of
rows at loop entry; `row-field` refers to that snapshot, while `lookup` reads the
current state. Nested iteration shadows the current row. State row order is
significant and determines effect order. Fields are sorted canonically. Named
actions must have unique IDs throughout a command, including nested branches;
loop iterations may repeat that ID in the trace. Branches and loops consume
fuel and their leaf actions contribute effects and trace entries.

The ledger fixture's postcondition compares `[sum-field "wallet" "balance"]`
with `[before [sum-field "wallet" "balance"]]`. Its explicit transfer record
implements idempotency and rejects a reused request ID with different arguments.
The engine supplies neither hidden deduplication nor hidden authorization.

## Judgments and guarantees

Shen's actual datatype checker judges expression, predicate, action, schema,
command and system construction. System admission also discharges scope
obligations: declared tables and fields, bound arguments, row-context use,
postcondition-only pre-state references, complete inserted records, unique
identities and bounded construction. These obligations are implemented as
Shen datatype side conditions. There is no Python operation interpreter.

Runtime evaluation checks preconditions, explicit requirements, schema
constraints, global invariants and postconditions. This is not a static theorem
that every well-formed operation preserves every invariant. An invariant failure
returns a rejected prospective transaction and no committed patch. Exploration
can expose such failures within the declared domain.

Each leaf instruction produces effects; the effect interpreter changes state.
The independent Python certificate checker reconstructs state from those effects,
checks that the trace concatenates to the effects, and checks actual writes and
emits against the native static upper bounds. It does not independently prove
predicates or trust an unverified supplied certificate. Recheck reruns all native
judgments and compares the exact evaluation, runtime and library identities.

## Requests, outcomes and traces

Input to evaluate/certify is an array of:

```json
{"command":"rename", "args":{"actor":"a","id":"i","title":"new"},
 "state":[{"table":"account","key":"a","fields":{"name":"Alice"}},
          {"table":"item","key":"i","fields":{"owner":"a","status":"open","title":"old"}}],
 "outcome":"committed"}
```

The argument names must exactly match the command declaration. An actor is an
ordinary argument whose authorization is specified by the model. It is not
authenticated by this engine.

| Outcome | Admissible observation |
| --- | --- |
| `committed` | Successful successor and all effects; none if model rejects |
| `aborted` | Pre-state and no effects |
| `unknown` | Pre-state/no effects and successful successor, if one exists |
| `rejected` | Pre-state/no effects only when the model rejects the command |

A result's `transition` is the prospective transaction, regardless of observed
outcome. Its `admissible` list applies the outcome. Rejection reasons include
precondition, explicit requirement labels and invariant failure. Missing fields,
unknown arguments, integer overflow and exhausted resources are operational
errors. They cannot be counted as a successful model rejection.

Optional `observed` is `{state,effects}`. Shen Prolog matches it against the
finite admissible alternatives. Ordered effects are:

- `["create",table,key,[[field,value],...]]`
- `["put",table,key,field,value]`
- `["delete",table,key]`
- `["emit",kind,payload]`

Optional `trace` is `{state,effects,steps:[{name,effects},...]}`. It must exactly
match native reconstruction. This checks the prospective execution trace; an
aborted observation still matches the pre-state/no-effects alternative.

## Workflows and bounded campaigns

A campaign supplies `initial`, `calls`, `depth`, and optionally `max_nodes`:

```json
{"initial":[{"table":"job","key":"j","fields":{"status":"pending","payload":"hello"}}],
 "calls":[{"command":"send","args":{"id":"j"},"outcome":"committed"},
          {"command":"ack","args":{"id":"j"},"outcome":"unknown"}],
 "depth":3,"max_nodes":256}
```

Breadth-first exploration considers every call at every frontier state and every
admissible outcome. Optional `schedule` supplies one list of call choices per
depth, allowing fixed workflows and bounded interleavings. States merge only at
the same depth; effects remain on every edge. Parent edges preserve witnesses.
The result includes all reached invariant failures and a shortest path to the
first one. A precondition rejection is reported separately from an invariant
failure. To continue after an expected rejection, include a call with outcome
`rejected`; a claimed commit of that rejected call has no successor.

`argument_domain` computes Cartesian products of explicit finite argument
values. It refuses an oversized domain instead of sampling. Campaign traversal
is host-side enumeration; all operation semantics and admissibility come from
Shen. No witness within these bounds is not unbounded correctness. There is no
claim of exploring undeclared values or hidden application state.

A single command models atomic state and intent commitment. Model non-atomic
workflows as separate commands, each with its own outcome. The outbox fixture
separates sending from acknowledgment and exposes repeated delivery attempts
before acknowledgment. The engine does not guarantee exactly-once delivery,
network determinism, linearizability, or scheduler completeness.

## Application harness and capcov integration

An adapter executable receives one JSON object on stdin:
`{"protocol":"capcov-system-adapter-v1","request":...}`. It must reset/prepare
the target, perform the requested operation, and return exactly `{state,effects}`
on stdout. Logs go to stderr. Processes have time/output bounds and run without
a shell. The adapter is explicitly selected executable code, not a sandbox.
Before launching it, the model and requests undergo native validation.

The harness records executable and file-argument digests and returns a certificate
binding normalized observations. It does not prove those observations faithfully
represent the target, nor capture all interpreter imports, remote binaries or
infrastructure. The consuming project must supply and review that mapping,
including transaction outcomes, row order, effect interpretation and scope.

`claims` first reproduces the certificate natively, then exports case-scoped
`system_case_matches` / `system_case_differs` evidence into a normal capcov Bundle.
The existing evaluator judges `system_case_conforms`; a missing observation has
no positive evidence, and a rejected trace supplies refutation. Certificate and
model identities are bound to the exported evidence. This is a claim about
normalized finite cases. It deliberately cannot mint operation-wide replay
qualification, completeness, reviewer admission or `model_operation_checked`.
Those existing contracts require their own explicit application adapter and
reviewer authority.

## Bounds and compatibility

1 MiB model, nesting 32, 4096 UTF-8 bytes/string, 64 tables, 512 commands,
64 fields/table, 64 named actions/command, 256 rows/state, 1–4096 action fuel,
256 requests/batch, 4 MiB request batch, 16 MiB process output, 1 MiB adapter
output, campaign depth 1–16 and up to 4096 nodes, 16384 edges and 32 MiB of serialized nodes/edges. Limits fail explicitly;
no truncated run is reported as complete. Timeout is per subprocess, not a
whole campaign deadline. Python core dependencies remain standard-library only.

The old single-operation `.op` API and frozen `model_min` remain available.
Static/observation/replay pack migrations and their existing evidence contracts
are not silently changed by this system engine. Native regression tests use the
Shen CI family; missing native tools are not accepted skips in that gate.
