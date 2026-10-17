# Production adapter contracts and induction

This milestone supplies reusable execution and proof boundaries. Application
mappings belong in the consuming repository. An adapter's declarations remain
claims about its implementation, not proofs that external services obey them.

## Adapter lifecycle

`capcov.operations.adapters.execute(payload, backend)` accepts the existing
`capcov-scenario-adapter-v1` executable history. It validates every call and
selected outcome before allocating resources. Expected model results are
rejected. The backend implements:

| Method | Contract |
| --- | --- |
| `describe()` | Return `identity`, `commands`, `outcomes`, `controls`. Identity must bind the deployed application, mapping, schema and fault-controller configuration. |
| `acquire()` | Allocate an exclusive disposable namespace and return its lease. Clean up partial allocation on error. |
| `reset(lease, initial)` | Seed the namespace, including resetting queues and effect cursors. |
| `snapshot(lease)` | Return model-shaped rows from a consistent observation boundary. |
| `execute(lease, index, call, outcome)` | Execute exactly once, inject the supported selected outcome, await the declared observation boundary, return `{outcome, observation: {state, effects}}`. |
| `release(lease)` | Destroy resources, even following failures. Failure invalidates the run. |

The runner checks reset against the initial snapshot, checks outcome
acknowledgment, validates observations, and checks the deployment manifest again
before accepting the history. The manifest digest is included in the existing
`controls` field so replay also compares the execution configuration. The
backend must actually enforce its isolation and fault contracts. Echoing an
outcome without enforcing it is an adapter bug; this library cannot establish
remote truth from an acknowledgment alone.

Do not obtain effects by differencing final snapshots: that loses ordering,
repeated writes and messages. Use an application journal, transactional outbox,
or instrumented boundary. Define whether effects describe committed logical
operations or attempted external interactions and align that with the model.
Use step indices to associate journal ranges, not to silently deduplicate
application behavior. Reject unsupported fault modes before execution.

For PostgreSQL/MySQL, use a disposable database/schema and application-owned
seed/snapshot mappings. A transaction opened in the adapter does not control a
separate service's connection. For Redis/DocDB and queues, allocate scoped
namespaces and coordinate snapshots at an explicit barrier. The consuming
adapter must define cross-store quiescence; independently reading stores is not
an atomic snapshot. Server leases need expiry and a reaper because client
cleanup cannot run after process death or a network partition.

## HTTP control plane

Run against an isolated test deployment with a consumer-owned control plane:

```sh
capcov reason scenario --spec app.ops --input scenario.json --timeout 90 \
  --adapter python -m capcov.operations.adapters \
  --url http://127.0.0.1:9080/control --timeout 60
```

All requests are JSON POSTs. Prefix the following paths with the configured URL:

| Path | Request | Response |
| --- | --- | --- |
| `/describe` | `{}` | Backend manifest above |
| `/sessions` | `{}` | `{"lease":"opaque_id"}` |
| `/sessions/{lease}/reset` | `{"initial":[...]}` | `{"ok":true}` |
| `/sessions/{lease}/snapshot` | `{}` | Model row array |
| `/sessions/{lease}/execute` | `{"index":0,"call":{...},"outcome":"committed"}` | Outcome and observation above |
| `/sessions/{lease}/release` | `{}` | `{"ok":true}` |

Responses must use HTTP 200. There are no automatic retries, redirects or
ambient proxies. Requests and responses are limited to 4 MiB. Deadline checks
occur before requests and between reads; a blocking read also has a socket
timeout. The scenario subprocess timeout supplies the hard wall-clock limit.
Cleanup has a separate five-second allowance. Use a scenario timeout longer
than the transport budget plus cleanup. A server-side expiry remains essential.

`--token-env CAPCOV_CONTROL_TOKEN` reads a bearer token from the environment;
tokens never enter evidence. HTTPS is required for bearer authentication outside
loopback. Keep this control plane inaccessible to ordinary application users.
Do not point reset operations at shared production data.

The regression fixture uses actual SQLite transactions behind a local HTTP
server. It exercises rollback, commit, reset verification, release and replay;
the native family checks its observed history against a Shen system model.
It is a synthetic consumer, not a ready-made mapping for a private application.

## Safety induction over arbitrary-length histories

`capcov reason induct --input transition-system.json --out proof.json` constructs
an induction certificate. `capcov reason check-induction --input proof.json`
rechecks it without loading proof search. The Python API additionally accepts
`check_induction(proof, system=expected_system)` to prevent theorem substitution.

The explicit transition-system schema has `variables`, `initial`, `invariant`,
`safety`, and a mapping of named `transitions`. Formulas use the existing
`atom`, `true`, `false`, `not`, `and`, `or` constructors. `next:x` denotes the
successor value of state atom `x`. Initial, invariant and safety predicates may
only refer to current-state atoms. For example:

```json
{
  "variables": ["valid"],
  "initial": ["atom", "valid"],
  "invariant": ["atom", "valid"],
  "safety": ["atom", "valid"],
  "transitions": {
    "preserve": ["or", ["not", ["atom", "valid"]], ["atom", "next:valid"]]
  }
}
```

For initial predicate J, invariant I, property P and every transition T, the
certificate proves:

1. Base: J entails I.
2. Safety: I entails P.
3. Preservation: I and T entail I with every atom renamed to its next-state form.

A small Shen composition rule reconstructs these sequents and checks every
derivation. Search results, status labels and artifact digests are not proof
premises. Artifacts bind the exact statement, component proofs, runtime,
propositional kernel and induction-rule hash. Missing, duplicated, reordered or
substituted obligations are rejected against the statement.

These premises establish safety for **every finite history**, without a history
length bound. Infinite executions consequently satisfy the invariant at each
finite position. There are no implicit frame conditions: a transition that
omits `next:x` permits either successor value of x. An unconstrained transition
can therefore make preservation fail. Countermodels identify failed propositional
obligations; they are not necessarily reachable application executions.

The proof language currently bounds the abstract state vocabulary to six
Boolean variables (twelve atoms including successors) and 64 transitions to fit
the existing propositional search budget. This limits abstraction size, not
execution length. False initial predicates or impossible transitions can yield
vacuous safety proofs; use witness search to establish nonvacuity separately.
The result does not prove progress, fairness or termination.

## Remaining implementation work

The generic transport and induction rule are usable now. These are distinct
remaining deliverables, not hidden premises discharged by these features:

* Consumer adapters: concrete private API routes, database mappings, cross-store
  barriers, journal cursors, lease expiry, and application fault hooks. Exercise
  committed, aborted, rejected and uncertain outcomes against actual services.
* Refinement: prove each concrete operation simulates the explicit abstract
  transition relation. Neither a user-written transition formula nor passing
  replay cases establishes source-to-model equivalence.
* General first-order/structural induction: add datatype constructors, quantified
  invariants, capture-avoiding substitution and checked induction hypotheses.
  The current feature is transition-system safety induction, not unrestricted
  Shen theorem proving over recursive datatypes.
* Loop integration now supports annotated snapshot-loop invariants with checked
  initiation, preservation and continuation obligations; see
  [loop-induction.md](loop-induction.md). Explicit processed/remaining relations,
  expression totality and fuel bounds remain separate work.
* Environment exploration: run these adapters under Antithesis or equivalent
  controlled scheduling and fault injection. Repeated identical observations
  remain replay evidence, not a proof of environmental determinism.
