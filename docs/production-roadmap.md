# Typed behavior and production verification roadmap

Planning revision: October 17, 2026. Baseline: `58ddd39b9edc5972855a3e3626fa818510e20bd5`, on
`shen-specification-foundation`. This is the execution plan for the reasoning,
induction, evidence and adapter extensions. It complements the existing capcov
plans; it does not declare the branch production-ready.

The governing design is [Executable typed behavior and migration contracts](typed-behavior-architecture.md). This revision moves typed executable behavior ahead of evidence admission: legacy behavior, intended behavior and the migration contract are distinct, connected artifacts. B1-B4 below add the missing critical path; W0-W11 retain the detailed production work. The R-series replaces the previous N-series execution order.

Status meanings: **implemented** means code exists; **validated** requires the
specified tests against a named revision; **production-ready** requires the
release gates below. Previous targeted test runs are not a substitute for a
current full pinned run. Milestones below are planned unless stated otherwise.

## 1. Intended result

One specification/evidence workflow should support the complete application
migration, not a single delete operation or a collection of disconnected demos:

1. Define reusable typed domain states, commands, effects and behavioral rules in Shen; inventory every route, background job, event consumer and external effect.
2. Maintain a reconstructed legacy model, an approved intended model and a versioned migration contract, sharing domain primitives while preserving intentional differences and unanswered questions.
3. Execute the model to generate simulations, histories and counterexamples.
4. Prove supported model obligations using independently checked derivations.
5. Exercise real implementations through isolated, observable adapters.
6. Connect each result to its source, model, runtime, environment and assumptions.
7. Refuse admission when evidence is missing, stale, incompatible or operationally
   invalid; show the specific missing obligation rather than a confidence score.
8. Repeat this for all inventoried behavior and invalidate affected evidence when
   code, specifications, adapters or checker semantics change.

The working application context is roughly 230 API paths, a PHP/MySQL legacy
system and a Go/PostgreSQL target, with DocDB and Redis. The exact inventory,
semantics and deployment contracts must be obtained from the consuming
repository. The existing specifications are valuable input, not presumed truth.

## 2. What exists and what is still missing

| Area | Implemented baseline | Remaining obligation |
| --- | --- | --- |
| Executable systems | Shen construction judgments, transactional action semantics, state/effect observations | Broader value/error semantics; application models and refinement |
| Propositional proofs | Search plus independent sequent checking | Quantifiers, equality, richer arithmetic and structural induction |
| History induction | Explicit Boolean transition systems | Derive/check abstraction from concrete operations; wider state theories |
| Loop invariants | Initiation, preservation, continuation; nested invariant loops | Stronger relational invariants and compiler-refinement evidence |
| Loop completion | Processed/remaining partition rule for row-local, current-key updates | Cross-key writes, insert/delete, nested completion and global selectors |
| Typing | Operation/model datatypes; completion formula/context/judgment datatypes | Typed claim elaboration and authority judgments; checker-function typing is separate |
| Evidence | Source anchors, identities, dependency invalidation, claim distinctions | Full route inventory, richer producers, durable lineage and admission policy |
| Soufflé | Existing translation, compiled cache and differential closure checks | Current full validation, extended relation schemas and dependency maintenance |
| Relational search | Finite Shen Prolog DSL with modes, cardinalities and affine capabilities | Better model integration, scoped symbolic generation and search guidance |
| Adapters | Lifecycle SDK, HTTP control-plane client, synthetic HTTP/SQLite tests | Enforced leases, service mappings, actual DB/queue barriers and fault hooks |
| Replay | Whole-history execution, explicit outcome choice, repeated observation comparison | Controlled time, entropy, scheduling and I/O; causal histories and durable replay bundles |
| Antithesis | Property catalog and SDK publication bridge | Provisioned campaigns, actual environment control and result ingestion |
| Runtime | Bifrost/Shen-Go process per request | Batching, measured caches, isolated workers, then justified incremental reuse |
| Release | Targeted native tests, lint and packaging checks from prior work | Full pinned CI, installation/upgrade tests and consuming-system qualification |

Current boundaries must remain visible until deliberately changed: propositional
proof validation allows 12 distinct atoms and 128 formula nodes; the Boolean
induction schema allows six state variables and 64 transitions. Scenario
transport allows 64 steps; model state validation allows 256 rows. Search has
separate depth/fuel/budget limits. Some proofs quantify over arbitrary finite
histories or snapshot lengths despite bounded execution tests. Raising an input
limit does not extend a proof theory, and finite search exhaustion is not an
unbounded unreachability proof.

## 3. Architectural decisions

* The primary artifact is a typed executable behavioral model. Rule contracts,
  effects, error paths and behavioral composition are checked object-language
  judgments; ordinary function types or structurally typed proof records are
  insufficient. Current implementation supports only part of this design.
* Model correctness, implementation conformance and migration preservation are
  separate obligations. Proofs about a model do not prove the PHP or Go program.
  Preserve raw observations and check concrete-to-domain mappings. Safety trace
  inclusion needs additional enabledness/progress obligations to exclude vacuity.
* Legacy, intended and migration artifacts have independent identities. Approved
  behavior changes require explicit decisions; agreement between implementations
  does not override a violated intended property.


* Shen owns logical judgments, proof checking, typed elaboration as it is added,
  and the reference model semantics. Prolog may propose derivations and search
  schedules; admission never trusts a search result without checking it.
* Python remains the host for transport, files, orchestration and the existing
  IR during migration. Current WP, capture and partition transformations are
  trusted code. Move their *authority* behind checked transformation witnesses,
  rather than assuming that changing implementation language proves correctness.
* Soufflé computes declared relational closures. It does not acquire permission
  to invent semantic premises, infer completeness from absence, or authorize a
  migration target. Preserve Python/interpreted/compiled differential checks.
* Keep a small, versioned checking surface. Document its axioms, primitive
  semantics and trusted dependencies. Formula datatype checking, validity of a
  derivation, compiler correctness and application refinement are distinct claims.
* Reuse content-addressed IR/evidence, producer distinctions, completeness and
  compatibility witnesses, frozen manifests and the marker transport. Preserve
  premise occurrences and explicit context mappings; compatibility is not
  automatically transitive.
* Public capcov contains generic engine code and synthetic fixtures. Private
  application models, mappings, deployment recipes and evidence stay in the
  consuming repository. Core remains standard-library-only; drivers are optional.
* Do not add an ELF/x86-64 framework, LuaJIT plugin runtime, alternate solver,
  hypervisor or language rewrite to the critical path. Each requires a separate
  justified decision. Host-level determinism is a later execution backend, not a
  property to infer from two equal replays.

## 4. Dependency order

| Work package | Prerequisites | Can proceed alongside |
| --- | --- | --- |
| W0: baseline and validation | Current branch | Consumer inventory and ambiguity collection |
| B1: domain language and model variants | W0 inventory; align W1 identities | W6 adapter lifecycle |
| W1: evidence/checker contracts | W0; B1 artifact vocabulary | B1, W6 |
| B2: checked rules and behavior composition | B1, W1 | W2, W3, W6 |
| B3: model execution, generation and correspondence | B2, supported W3 witnesses | W6-W7, consumer models |
| B4: migration contracts and three-way qualification | B1, B3, W1; real execution needs W6 | W9 rollout |
| W2: typed claims and authority | W1, B1 sorts; integrate B2 derivations | W3, W6 |
| W3: checked compiler transformations | W1, B1 semantics | B2, W2, W6 |
| W4: quantified/structural induction | B2, W2 conventions, W3 boundary | W6-W8 |
| W5: general frames and completion | W3, relevant W4 theories | W10 |
| W6: production adapter enforcement | W0; W1 envelope and B1 domain mapping alignment | B1-B4, W2-W5 |
| W7: deterministic controls and replay | W6, B3 choice semantics | W4-W5, W9 |
| W8: concurrency and temporal properties | B2 composition, W7, relevant W4 theories | W9 |
| W9: complete application migration | Start inventory now; B4 and W6 for qualification | W7-W8 |
| W10: performance and incrementality | W0 metrics, W1 and B1 identities | After each semantic increment |
| W11: release qualification | All advertised capabilities; W9 consuming evidence | Final admission gate |

Development can overlap where shown. Admission requires the relevant gates, not
completion of every future proof theory. B1-B4 describe planned work, not new
runtime functionality delivered by this documentation revision.

### B1 — Typed domain language and distinct behavioral models

Define sorted domain values, state schemas, commands, errors, effects, capabilities,
footprints and predicates, with explicit numeric/partial-expression semantics.
Add source-mapped canonical behavior IR and an explicit versioned `.ops` bridge.
Represent legacy and intended variants as shared primitives plus named differences;
bind each claim to its precise variant. Keep unresolved specification clauses
first-class and do not infer completeness from having mapped every URL.

**Deliverables:** language/IR version, Shen construction judgments, primitive
semantics, model-variant manifests and old/new compatibility fixtures. Start with
existing state/action constructors; expand them without silently changing v1.

**Gate:** valid/invalid declarations, scope/sort/effect errors, raw-to-domain value
round trips, variant identity isolation and semantic agreement for translated old
models. An omitted error branch is an obligation, not implicit success.

**Touchpoints:** `operations/system.py`, `shen/system-types.shen`,
`shen/system.shen`, existing operation datatypes; proposed behavior elaborator and
versioned IR modules. New paths are design proposals until implemented.

### B2 — Typed rule contracts and checked behavior composition

Implement the object-language judgment described in the architecture document.
Separate structural well-formedness, contract derivability and execution outcome.
Define trusted primitive rules and checked derived rules, then sequencing,
branching, frames, transactional commit/abort, effects and resource accounting.
Integrate existing loop proofs; add retry/idempotency, recursive and concurrent
rules only with the relevant W4/W5/W8 obligations. Unsupported contracts stay open.

**Deliverables:** frozen primitive/axiom ledger, rule declaration syntax, explicit
proof terms, independent checker, elaboration diagnostics and reusable behavior
library. Libraries cover ownership, CRUD, transactions, idempotency, outbox/worker
flows, snapshot iteration, retries and compensation as their gates become available.

**Gate:** check compositions with proof search disabled; reject arbitrary user
axioms, missing branch/error cases, false frame conditions, capability duplication,
circular lemmas and incompatible pre/post composition. Publish which checks are
mechanized and which semantic correspondence arguments remain trusted.

### B3 — Shared execution, generation and conformance semantics

Execute canonical behavior IR in the reference Shen interpreter. Generate legal
inputs/histories through typed modes and finite constraints; label invalid-input
campaigns separately. Emit transition witnesses and typed effect requests. Derive
obligations and finite graph/relation projections from that same model, retaining
translation witnesses or explicit trust boundaries under W3.

Define adapter observation maps for arguments, returns, errors, state and effects,
including hidden transitions and pending outcomes. A conformance monitor tracks
allowed model states and reports budget exhaustion as open. Preserve raw events.
Do not normalize away effect multiplicity, ordering or externally visible errors.

**Gate:** simulator/generator/checker agreement on supported fragments; mutant
models and adapters rejected; ambiguous commit retains alternatives; unreachable
preconditions are reported separately from vacuous partial correctness. Conformance
results name concrete histories; universal refinement requires a separate argument.

**Optional planner gate:** pin and validate GraphWalker schema/generators, export a
finite abstraction, map path proposals back to model transitions and concrete
inputs, then validate execution. Failed feasibility search remains open. Souffle
projections preserve unknowns/completeness and existing differential checks. Neither
engine becomes the authority for behavioral judgments. ELF is a separate producer.

### B4 — Explicit migration contract and three-way qualification

Create versioned preserve/change/remove/defer decisions binding legacy and intended
clauses, observation mappings, rationale, approval provenance and obligations.
Run model, legacy and target on comparable scenarios and classify disagreements.
Check target safety refinement plus declared supported-operation and progress
requirements; use equivalence only where specifically required. Legacy defects
must not force rejection of an approved correction or disappear from reporting.

**Deliverables:** decision schema, three-way report, per-capability obligation
matrix, source/specification ambiguity queue and dependency invalidation rules.

**Gate:** synthetic transfer/outbox/retry workflow with a legacy duplicate-effect
bug, intended correction and explicit decision. Detect a target mutant, a shared
legacy/target bug, missing approval, incomplete mapping and replay identity drift.
Then apply the same contract to real consumer capabilities under W9. One passing
fixture validates integration only; it does not qualify the full migration.

## 5. W0 — Establish the actual baseline

**Deliverables**

* Run the current revision through the pinned flake/tool-family CI, including
  Shen, Soufflé, indexers, packaging and the skip-accounting gate.
* Record tool/runtime hashes, test discovery counts, expected skips, failures,
  platform and timings. Resolve toolchain failures separately from test failures.
* Capture representative benchmarks: cold Shen startup, elaboration, sequent
  checking, loop checking, relational search, closure evaluation and adapter replay.
* Audit current rejection behavior: malformed or truncated records, stale hashes,
  unknown constructors, mismatched theorem/model bindings and resource exhaustion.
* Record current certificates as compatibility fixtures, with explicit expectations
  for which checker/compiler changes require regeneration.

**Gate:** every discovered test is accounted for exactly once by the family gate;
no unexpected skips; installed-wheel tests exercise native resources. No claim
of a clean full baseline while a family remains unexecuted. Timing data is the
basis for later performance budgets, not an estimate from a few examples.

**Touchpoints:** `.github/workflows/ci.yml`, `flake.nix`, `tests/tool-families.json`,
`scripts/check-skips.py`, `scripts/check-wheel.sh`, `tests/shard-timings.json`.

## 6. W1 — Version evidence and checker contracts

Define a common envelope without erasing the distinctions between artifact kinds.
Use Model, Claim, Obligation, Proposal, Evidence and Judgment records. Bind legacy/
intended variant, migration decision, behavior/rule identity and observation mapping
where applicable. W1 standardizes transport; B1/B2 define behavioral meaning:


* Statement/model identity; context and assumptions; proof or observation scope.
* Source revision and extraction identity; producer class and producer version.
* Runtime, checker, rule pack, compiler and adapter/environment identities.
* Dependency identities, completeness/compatibility witnesses and occurrence IDs.
* Budget/termination information, operational result and semantic result.
* Canonical serialization version and artifact digest. A digest is identity and
  integrity evidence, not authentication of a remote producer.

Introduce structured results for proved, refuted, open, bounded-exhausted and
inapplicable semantic outcomes, separately from successful execution, timeout,
unsupported input, unavailable tool, protocol failure and identity drift. A
countermodel of a proof obligation is not automatically a reachable application
counterexample. An unreachable command may have vacuous correctness; preserve
reachability witnesses separately.

Add explicit schema migration/read compatibility rules. Existing v1 artifacts
must either be checked under their pinned semantics, be explicitly re-elaborated,
or be rejected with a version reason. Never silently reinterpret them.

**Gate:** adversarial envelope tests cover omitted assumptions, theorem swaps,
source swaps, forged hashes, changed producer classes and cross-version replay.
Failure cannot become a successful claim through folding or CLI exit handling.

**Touchpoints:** `claims/ir.py`, `claims/authority.py`, `operations/proofs.py`,
`loops.py`, `induction.py`, `evidence.py`, `scenarios.py`, `workbench.py`.

## 7. W2 — Extend genuine Shen typing into claim elaboration

Integrate B1 domain sorts and B2 behavioral derivations into evidence admission.
Behavior validity and producer authority remain separate checked judgments.
Build typed judgments around existing semantics rather than copying the untyped
authority code and relabeling its column checks as a type system.

**Implementation sequence**

1. Define Shen datatypes for sorted terms, relation signatures, contexts, premise
   occurrences, producer declarations and rule syntax.
2. Define explicit judgments for well-formed bindings, allowed joins, producer
   authority, compatibility mapping and closed-world negation with a matching
   completeness witness.
3. Elaborate readable claims into canonical typed IR plus derivation records.
   Keep unification variables distinct from bound variables and source names.
4. Check those derivations independently. The conclusion includes the exact
   context and occurrence mapping; it cannot be reused for a different join.
5. Differentially compare Python, existing Shen and the new typed elaborator on
   all current packs and generated invalid packs. Classify intended changes.
6. Migrate pack families in separate changes. Freeze and verify manifests after
   each migration. Remove an old admission path only after its replacement gate.

Typing a judgment's data structure is the first step. Explicitly enumerate which
semantic rules are checked and which checker functions remain untyped/trusted.
Do not equate function typechecking with a proof of logical soundness.

**Gate:** all supported existing packs elaborate/check; negative fixtures reject
producer escalation, missing completeness, incompatible context, duplicated or
substituted premise occurrences and illegitimate compatibility transitivity.
No disagreement is resolved by silently selecting the most permissive engine.

**Touchpoints:** `claims/spec/`, `shen/claim-workbench.shen`, `shen/rule-authority.shen`, `shen/evidence-authority-v2.shen`,
new claim datatype/checker modules, `tests/claim_semantics/authority_v2/`.

## 8. W3 — Reduce trust in compilation and abstraction

Make each transformation produce a checkable witness:

| Transformation | Required witness/check |
| --- | --- |
| Assignment WP | Exact location, substitution and expression semantics |
| Frame simplification | Declared read/write footprint and proved disjointness |
| Universal instantiation | Binder, term sort, scope and existence conditions |
| Snapshot substitution | Head-of-remaining relation and immutable captured values |
| Arithmetic normalization | Exact equality steps plus applicable numeric-domain conditions |
| Loop composition | Initiation, body preservation, completion and continuation edges |
| Model abstraction | Concrete-to-abstract relation and transition simulation obligations |

Start with current accepted cases, then move trusted Python decisions behind
these witnesses one constructor at a time. A Shen checker must reconstruct the
required judgment rather than trusting a compiler-supplied “safe” flag.

Generate small well-formed programs and states and compare symbolic results with
the executable Shen interpreter. Include aliasing, absent rows, snapshot staleness,
`before`, partial arithmetic, abort paths and zero-iteration loops. Seed mutants
that intentionally make a rewrite unsound and require detection. This tests the
boundary; it does not replace a general refinement proof.

**Gate:** every admitted transformation identifies its rule and prerequisites;
unsupported transformations stay open. Maintain a shrinking trusted-code ledger.
For each claimed mechanically verified transformation, supply the actual checked
refinement derivation, not only passing differential tests.

## 9. W4 — General quantified and structural induction

### W4a: Terms, binders, equality and quantifiers

Introduce a small sorted first-order term language. Specify bound-variable
representation, alpha-equivalence, fresh eigenvariables, capture-avoiding
substitution, occurs checks and scope explicitly. Add checked equality,
congruence and quantifier rules before adding ambitious search automation.

Keep proof production separate from checking. Shen Prolog can search for lemma
instances and derivation trees with explicit modes, budgets and failure reasons.
No fuel cutoff is logical falsity. Separate proof-checking resource limits from
proof-search heuristics; raising the current 12-atom cap is not this milestone.

**Gate:** alpha-renaming invariance; rejected variable capture, escaping
witnesses, circular substitutions and invalid quantifier instantiations; valid
examples independently checked with proof search disabled.

### W4b: Datatypes and recursive reasoning

Add approved strictly positive datatype declarations, constructor disjointness
and injectivity, exhaustive cases, and structural-induction rules. Begin with
lists, naturals and finite maps with explicit key-uniqueness invariants. For each
constructor, instantiate induction hypotheses only for its recursive subterms.
Later add mutually recursive types with explicit joint coverage and measures.

Support lemma packages and reusable proofs indexed by statement/context/kernel
identity. Reject self-justifying lemmas and cyclic proof dependencies. Prove
termination separately when claiming total correctness; recursive search and
partial-correctness judgments do not establish termination.

**Gate:** checked list-fold/map/delete proofs, finite-map update properties and
recursive protocol examples; negative tests for missing constructors, using an
induction hypothesis on the original/larger term and forged decreasing measures.

### W4c: Arithmetic, modes and resources

Specify integer widths, canonical representation, overflow and failure behavior.
Extend beyond current int32 only through an explicit semantic version. Add
checked arithmetic certificates for the supported fragment; start with exact
linear equalities/inequalities and range obligations. Treat unsupported nonlinear
or aggregate reasoning as open.

Connect mode/determinism and affine-capability judgments to operation inputs,
resource ownership and effect permissions. Distinguish a static upper bound on
solutions from measured execution behavior. Check capability splits/joins and
consumption across branches rather than trusting annotations.

**Gate:** conservation and range proofs, rejected overflow shortcuts, correct
branch-resource accounting and concrete witnesses for satisfiable preconditions.

## 10. W5 — General completion, frames and domain changes

Replace syntactic current-key locality with checked relational footprints.
Introduce proof-level relations for selected, processed, remaining, inserted and
deleted keys, with explicit disjointness, membership and cardinality facts.

Ordered increments:

1. **Disjoint cross-key updates:** prove key inequalities and ownership; retain
   processed-row facts only where the write footprint is disjoint.
2. **Deletion:** distinguish “processed successfully,” “still present,” and
   “absent as specified.” Update coverage and existence obligations explicitly.
3. **Insertion:** distinguish the captured iteration domain from the evolving
   live domain; prove obligations for newly inserted rows separately.
4. **Nested completion:** establish inner/outer footprint separation and snapshot
   lifetimes; support aliasing only through checked relational conditions.
5. **State-dependent selectors:** bind selector evaluation to the capture state;
   prove when current-state conclusions follow from historical membership.
6. **Relational/aggregate results:** prove mappings between old/new rows, counts,
   conservation and ordering where the model exposes ordering.
7. **Total correctness:** derive structural/lexicographic measures and fuel bounds
   for supported bodies, while keeping rejection and expression traps explicit.

**Gate:** each relaxation of the current frame restriction comes with a positive
proof and an adversarial near-match that fails. Regress cross-row corruption,
reinserted keys, duplicate keys, deleted-yet-referenced rows, stale selectors and
nested aliasing. Do not broaden the constructor allowlist before its rule exists.

**Touchpoints:** `operations/completion.py`, `loops.py`, `compiler.py`, the Shen
loop/checker datatypes and executable `system.shen` semantics.

## 11. W6 — Enforce production adapter contracts

### W6a: Lease and identity enforcement

Add a reusable control-plane server foundation around the existing client/SDK.
Use exclusive disposable namespaces, bounded leases, expiry, fencing against
stale clients and a reaper. Partial allocation must be recoverable after client
or server death. Bind deployed application, mapping, schema, journal and fault
controller versions to the manifest.

Version the protocol before adding semantic fields. Define request/step IDs,
duplicate-request behavior and crash recovery. Never automatically retry a
mutating call after an ambiguous response; reconnect may query its recorded
status without re-executing it. Redact credentials from artifacts and errors.

**Gate:** crash at every lifecycle stage, expired/stolen leases, simultaneous
sessions, reset mismatch, deployment drift and cleanup failure. Prove isolation
through independent observations; an adapter's `controls` declaration is not
sufficient evidence of enforcement.

### W6b: SQL and effect journals

Provide generic PostgreSQL and MySQL integration points, with actual seed/read
mappings in the consuming repository. Test against pinned real services, not
only SQLite. Exercise transaction rollback, committed-but-response-lost outcomes,
uniqueness, foreign keys, concurrent writes and schema-version drift.

Use ordered journal/outbox records with step/attempt/transaction identity. Distinguish
logical effects, attempts and acknowledgments. Do not reconstruct effect order
from final-state diffs or deduplicate away the behavior being tested. Specify
journal completeness and cursor boundaries as evidence-producing contracts.

### W6c: Redis, DocDB and queues

Define per-run namespace ownership, TTL/clock handling, read consistency,
background-worker drain/barrier behavior and external message capture. Integrate
actual services where their semantics matter; a substitute service's result is
labeled as substitute evidence. Independently read stores are not an atomic
snapshot: declare the observation cut and prove/enforce the required barrier.

**Gate for W6b/c:** multi-store histories with delayed delivery, duplicate delivery,
partial commit, retry and worker restart are observable and replayable within
stated controls. Missing journal ranges or an unestablished barrier invalidate
the evidence instead of becoming empty effects.

**Ownership:** engine contracts and synthetic service fixtures are public;
application routes, schemas, credentials and orchestration remain private.

## 12. W7 — Controlled replay and fault exploration

Define a versioned choice/event tape covering virtual time, entropy, logical
schedule, request/response delivery, retry timing, process restarts and effect
acknowledgments. Separate nondeterministic input events from expected outputs.
Bind every replay to the exact binaries/configuration/data seed and control scope.

Keep two distinct execution modes:

* **Forced campaign:** the harness controls an outcome and records evidence of
  the injection point and resulting observations.
* **Observed execution:** the real outcome may be unknown. Preserve the allowed
  alternatives until observations resolve them; do not pretend an unknown commit
  followed an arbitrarily chosen branch of the tape.

Implement controls first at application/transport boundaries. Detect or declare
uncontrolled clocks, random sources, workers and network paths. A hermetic claim
requires evidence that the relevant I/O cannot bypass interception. Add stronger
container/VM backends only against an explicit threat/control model.

Persist self-contained replay bundles and minimization artifacts. Minimize under
causality, prerequisites, resource lifetime and a stable failure identity, not
only matching the name of the first failing command. Verify the minimized case
in a fresh environment and report exhausted reduction budgets honestly.

**Gate:** reproducible schedule-sensitive failures; rejection of missing tape
entries, divergence, build drift and hidden control changes; injected real faults
rather than outcome acknowledgments alone. Antithesis campaigns ingest the same
property IDs/artifacts without upgrading observations into proofs.

## 13. W8 — Concurrency and temporal properties

Add invocation/completion intervals, actor/transaction IDs, causal edges and
explicit pending operations to histories. Define each consistency contract
separately: linearizable operations, transactional isolation, causal ordering or
specified eventual convergence. Do not force all stores into one consistency model.

Extend relational search to legal concurrent schedules and admissible
linearizations, with explicit bounded exploration. Add partial-order reduction
only when dependency/commutativity premises are checked. Keep uncertain commits,
cancellation and duplicated delivery in the model.

For liveness, record the fairness, delivery and scheduling assumptions. Distinguish
finite-time “eventually observed” properties from unbounded progress theorems.
Add ranking/well-founded arguments for supported protocols; never report passing
bounded campaigns as a general liveness proof.

**Gate:** independent small-history oracle comparisons; classic lost-update,
double-spend, duplicate-delivery and retry races; histories where no valid
linearization exists; incomplete histories that remain unresolved.

## 14. W9 — Integrate the whole application migration

Build a canonical inventory in the consuming repository, starting with the
reported 230 routes and reconciling the actual count. Include route variants,
authorization roles, validation branches, jobs, timers, events and dependencies.
A path count alone is not behavioral coverage.

For every entry record: legacy source anchors, specification clauses, target
intent, model command(s), argument/result/error mapping, affected resources,
invariants, effects, adapter mapping, proof obligations, campaigns, evidence
producers and unresolved questions. Unsupported or intentionally removed behavior
must be visible with a disposition; it cannot vanish from the denominator.

Use the B4 migration contract and classify three-way outcomes, including shared
legacy/target defects and approved differences. Every entry names its legacy and
intended variant, decision identity, observation map and remaining obligations.

Separate three relations:

1. Source/specification to model: assumptions and refinement obligations.
2. Legacy implementation to legacy model: preservation evidence.
3. Target implementation to approved target model: conformance evidence.

Intentional changes require explicit compatibility/promotion decisions. A legacy
bug is neither automatically the target specification nor silently “fixed” during
normalization. Version HTTP status/error bodies, pagination, ordering, identifiers,
null/missing values, integer encodings and timestamp normalization. Compare
semantics, while retaining raw observations for audit and debugging.

Roll out by interacting capabilities: account/ownership, CRUD and cascading
behavior, idempotent commands, outbox/worker workflows, then cross-store and
concurrent scenarios. These are rollout groups, not the final scope. Finish every
inventory entry and its declared critical behavior.

**Gate:** all entries have traceable dispositions; critical target obligations
meet the agreed evidence policy; mismatches have reproducible minimized cases;
source/model/adapter changes invalidate precisely identified dependencies.
Unresolved critical semantics block target admission. Report proof scope and
bounded test scope explicitly, not “90% confidence.”

## 15. W10 — Performance without weakening evidence

**Order:** measure, batch, cache, isolate workers, then incrementally maintain.

1. Batch independent native checking jobs under an immutable environment. Compare
   results with one-request-per-process execution, including individual failures.
2. Cache immutable elaborations and checked artifacts with complete identities:
   statement, assumptions, input facts, compiler, checker, runtime and dependencies.
   Store budget/operational results separately; a timeout is not a theorem cache hit.
3. Evaluate workers keyed to a frozen model/rule environment. Bound memory, fuel,
   wall time and output; kill/restart corrupted workers. Test Shen global bindings,
   function redefinition, Prolog state, exceptions and cross-request leakage.
4. Add dependency-directed invalidation and incremental relation maintenance.
   Handle removals, negative premises and completeness-witness changes, not only
   new facts. Compare incrementally updated results with full recomputation.
5. Track p50/p95 elapsed time, native launches, proof nodes, memory, cache hits
   and invalidation fan-out on the real workload. Set budgets from W0 measurements.

**Gate:** cold/warm/batched/worker/incremental modes agree semantically under fault
and mutation tests. Cache corruption and incomplete dependencies fail closed.
Persistent execution is not called “incremental evaluation” until dependency-aware
reuse itself is implemented and validated.

## 16. W11 — Qualification and release

A release claiming the full workflow requires:

* A green current pinned CI matrix with all tests and accepted skips accounted for.
* Reproducible installable artifacts containing every checker, datatype and frozen
  resource; installed-wheel native tests outside the checkout.
* Documented language, protocol and certificate versions and tested upgrade/refusal
  paths for prior artifacts. Changed checker semantics cannot silently reuse proofs.
* Real-service qualification of the adapter/control scope actually advertised.
* Cold restoration of replay bundles, crash recovery, cleanup and identity checks.
* Checked B1/B2 behavior/rule judgments and B3 correspondence boundaries, with
  versioned B4 migration decisions; distinguish model proofs from implementation evidence.
* A consuming application report that covers its entire reconciled inventory and
  keeps unresolved/unsupported cases visible.
* A trusted-code/assumption ledger with no undocumented semantic authority.
* Operational guidance for diagnosis, resource limits, cleanup, rollback and
  regeneration of invalidated evidence; private credentials absent from exports.

Release labels must name their scope. “Qualified for the declared controls and
model fragment” is assessable. “Full general induction” or “deterministic arbitrary
cloud applications” is not justified by the current implementation or this plan.

## 17. Concrete change sequence

This R-series supersedes N01-N19 from the previous roadmap. All original work
packages remain above; the revised order adds typed behavior as the common basis.
Each row is a reviewable change or small series. Dependencies gate admission.

| ID | Change | Depends on | Exit evidence |
| --- | --- | --- | --- |
| R01 | Full pinned baseline, trust inventory and benchmarks (W0) | Current branch | Accounted test families and named validation report |
| R02 | Typed domain/behavior IR, variants and `.ops` compatibility (B1) | R01 | Construction and compatibility fixtures |
| R03 | Common artifacts, outcomes, mappings and decision identities (W1) | R02 vocabulary | Cross-version/adversarial envelope checks |
| R04 | Primitive contract rules and composition checker (B2) | R02, R03 | Independent valid/forged derivation checks |
| R05 | Checked WP/frame/substitution transformation protocol (W3) | R02, R03 | Checked rewrites and mutant detection |
| R06 | Typed claims, authority and pack migration (W2) | R03, R04 | Differential admission and occurrence checks |
| R07 | Shared simulator, typed generation and conformance monitor (B3) | R04, R05 supported fragment | Cross-interpretation and ambiguity checks |
| R08 | Enforced leases, fencing and server lifecycle (W6a) | R01; align R03 | Crash, expiry, cleanup and isolation suite |
| R09 | Real SQL transaction/journal adapters and domain maps (W6b) | R08, R02 | Real MySQL/PostgreSQL outcome tests |
| R10 | Migration decisions and three-way integration (B4) | R07, R09 | Transfer/outbox/retry fixture and target mutants |
| R11 | Sorted quantifier/equality kernel (W4a) | R04, R05 | Binder/eigenvariable/definedness adversarial checks |
| R12 | Structural induction, arithmetic and resource lemmas (W4b/c) | R11 | Constructor coverage, range/conservation proofs |
| R13 | Cross-key, domain-changing and nested completion (W5) | R12, R05 | Valid proofs and invalid-frame countercases |
| R14 | Redis/DocDB/queues and consistent observation cuts (W6c) | R09 | Real-service barriers and journal completeness |
| R15 | Controlled choices, uncertainty and durable replay (W7) | R07, R09, relevant R14 controls | Fresh-environment fault replay |
| R16 | Causal minimization and Antithesis round trip (W7) | R15 | Reduced reproducible failures and imported evidence |
| R17 | Concurrent behaviors, histories and temporal contracts (W8) | R04, relevant R12 theories, R15 | Independent small-history oracles and progress assumptions |
| R18 | Souffle-guided targeting and optional GraphWalker projection (B3) | R07, R06; R15 for replay claims | Projection mapping, feasibility and seed/control distinction |
| R19 | Full consumer inventory, decisions and evidence rollout (W9) | Inventory now; R10 for qualification | Every entry disposed; critical gaps resolved |
| R20 | Batch, cache and isolated workers (W10) | R01, R03, stable relevant semantics | Measured cross-mode agreement |
| R21 | Incremental fact/proof/decision invalidation (W10) | R06, R05, R20 | Full recomputation agreement including removals |
| R22 | Complete release qualification (W11) | All advertised capabilities and R19 | Scope-specific release bundle |

**Immediate next work:** R01, then R02/R03 as a coordinated schema increment,
followed by R04/R05/R07. Start R08 and consumer inventory alongside that work.
R10 is the first complete behavioral migration loop, not the release endpoint.
R11-R17 extend its proof and execution coverage; R19 covers the whole application.
R18 is optional and must not block required consumer qualification. R22 requires
it only if that integration is advertised. Do not substitute another isolated
example or a larger Boolean search bound for the behavioral-language milestone.

## 18. Migration, rollback and stop conditions

Run replacement elaborators/checkers in shadow comparison first. Do not make a
new authority path the default until its compatibility fixtures and negative
admission tests pass. A checker disagreement blocks admission and produces a
reproducible artifact; it does not trigger fallback to a more permissive engine.
Legacy verification remains an explicitly versioned mode with its original scope.

Keep published evidence immutable. Promote or roll back a manifest pointer to a
named compatible bundle; never rewrite an old proof to look as if a new checker
produced it. Regenerate affected evidence after semantic changes. Adapter and
control-plane rollbacks must preserve namespace cleanup and fence obsolete leases.

| Risk | Required response before expansion |
| --- | --- |
| Logical rule is unsound or scope is ambiguous | Freeze admission of affected artifacts; add a counterexample, fix the checker and invalidate dependent proofs. |
| Search blows up | Return open/budget-exhausted; add lemmas or decomposition. Never weaken the goal or call the cutoff a refutation. |
| Adapter cannot establish a consistent observation | Record operational invalidity; fix the barrier/journal contract before using results as conformance evidence. |
| Private behavior remains ambiguous | Keep the claim unresolved with an owner and affected inventory entries; block critical target promotion. |
| Persistent worker leaks state | Disable that execution mode; reproduce against cold processes before re-enabling it. |
| New datatype/checker resource is missing from installation | Fail installed-package validation and release; no host-language semantic fallback. |
| The implementation effort is diverted into another runtime/tool | Require a measured gap, explicit scope and its own acceptance gate before adding the dependency. |

## 19. Inputs and decisions still required

Public engine work can proceed now. Production qualification needs access to the
consuming repository, deployment recipes, actual route/job inventory, sanitized
seed data, schema/migration definitions, external-effect boundaries and owners
who can resolve specification ambiguities. These are concrete dependencies, not
reasons to stop generic engine development.

Resolve before the relevant gate: which target language/runtime is authoritative;
which service versions/consistency contracts are deployed; which intentional
behavior changes are approved; the required concurrency/fault model; which
critical claims require proof versus bounded evidence; and where long-lived
artifacts are retained. Record decisions with identities and affected claims.

Optional branches stay separately budgeted: GraphWalker path planning, LuaJIT plugins, ELF/x86-64 extraction,
alternate Shen runtimes, external solvers and VM-level deterministic execution.
Adopt one only when a measured gap or an explicitly chosen product requirement
justifies it, with its own evidence and compatibility gate.
