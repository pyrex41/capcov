# Executable typed behavior and migration contracts

Design revision: October 17, 2026. This document specifies the next architecture;
it does not claim these features are already implemented. The code baseline is
`7b18a978d5bab624249ae290846be25c5933846f`; no validation is recorded at that
revision. See the [production roadmap](production-roadmap.md) for ordered work and
release gates, and the [glossary](#10-glossary) for terms.

## 1. Purpose

Make Shen the executable definition of allowed application behavior. Use that
same definition for simulation, legal scenario generation, model proofs,
implementation conformance, and migration decisions. capcov's evidence machinery
records exactly which obligations have been established, under which assumptions.

The working consumer has approximately 230 API paths, PHP/MySQL legacy behavior,
and a Go/PostgreSQL replacement, with DocDB and Redis. Public capcov supplies the
language, interpreters, checkers and adapter contracts; application-specific
models, schemas, decisions and execution evidence belong in the consumer repo.

The reusable result is a behavioral verification system. Port qualification is
one application. Basic-block analysis is another possible producer of evidence;
it does not determine the core language or replace domain semantics.

## 2. Three specifications, explicit relationships

| Artifact | Meaning | Authority and uncertainty |
| --- | --- | --- |
| Legacy model | Reconstructed behavior of the existing application | Source analysis and observations support scoped claims; unobserved behavior remains unknown. |
| Intended model | Approved domain behavior and requirements | Requirement owners resolve ambiguities; the current prose specification is input, not an oracle presumed correct. |
| Migration contract | Preservation requirements, approved changes, unsupported cases and rollout policy | Every behavioral difference has a versioned disposition, rationale and affected obligations. |

Share domain types, primitives and invariant libraries. Represent genuine
legacy/target differences as named, immutable variants or overrides with explicit
contracts. Avoid copying two entire models and allowing them to drift. Do not
force a legacy bug into the intended invariant merely to make validation pass.
A legacy variant may intentionally lack that invariant; its counterexample is a
finding, while the target variant must establish the stronger property.

A migration decision is an artifact, not a comment suppressing a failing test.
It binds old/new clauses, input and observation scopes, compatibility policy,
owner/approval provenance, rationale and replacement obligations. Proposed
changes are not approved changes. Changes to a decision invalidate its dependents.

## 3. Typed behavioral language

The language should represent the following as first-class typed terms:

* Domain values: identifiers, money, timestamps, optional/missing values, records,
  tagged errors and collections. Numeric widths and overflow are explicit.
* State: entities, keys, relationships, invariants and ownership regions.
* Commands: typed inputs/results, authorization context and capability requirements.
* Expressions/predicates: sorted terms, binders, historical-state references and
  definedness conditions; partial arithmetic cannot become a total logical axiom.
* Primitive behaviors: reads, writes, require, branches, iteration, transactions,
  effect emission, failure and nondeterministic/environment choices.
* Rule contracts: preconditions, normal/error postconditions, read/write footprints,
  effect allowances, resource consumption and applicable assumptions.
* Composite behaviors: sequencing, alternatives, recursion, retries, workflows,
  concurrency and compensation, with explicit composition obligations.
* Properties: state invariants, transition relations and temporal/history contracts.

An illustrative contract (design notation, not runnable Shen syntax):

```text
transfer(from: AccountId, to: AccountId, amount: PositiveMoney)
  requires distinct(from, to), accounts-exist(from, to), balance(from) >= amount
  atomic debit(from, amount); credit(to, amount)
  returns TransferReceipt
  ensures total-balance = before(total-balance), balances >= 0
  emits TransferCompleted
  writes accounts[from].balance, accounts[to].balance, transfer-outbox
```

Specify whether emission is an atomic outbox write or an external delivery;
external delivery is not made transactional by this notation. Define failure
outcomes, receipts and retry identity before calling the contract complete.

The central schematic judgment is:

```text
Gamma ; resources |- behavior : {pre} result ! effects {normal-post, error-posts}
```

This is a proposed object-language judgment implemented in Shen, not a claim that
Shen's ordinary arrow types already express Hoare logic. The initial judgment
provides partial correctness. Termination/progress requires additional checked
arguments. A structurally well-typed contract may still have open proof obligations.

Keep four results separate: well-formed term; valid contract derivation; model
execution outcome; implementation conformance evidence. A datatype checking the
shape of a proof record establishes only the first result.

## 4. Typed rules and trusted primitives

Separate constructors of behavioral syntax from the rules that justify contracts.
Give each primitive operational semantics and a corresponding contract rule.
For primitives retained as axioms, publish the exact axiom and its trusted
implementation. Derived rules carry proofs checked against that primitive basis.
Users cannot register an arbitrary conclusion as a trusted rule merely by giving
it a well-formed signature.

Composition rules must establish, at minimum:

| Construct | Required obligation |
| --- | --- |
| Sequence | First postcondition implies second precondition; compose effects and resources. |
| Branch | Guard scoping, branch coverage, definedness, and compatible result/postcondition joins. |
| Frame | Actual writes are disjoint from the state supporting preserved assertions. |
| Atomic block | Model commit/abort semantics; adapter correspondence is a separate obligation. |
| Retry | Attempt identity, ambiguous outcomes, idempotency and externally repeated effects. |
| Iteration/recursion | Invariant, frame, completion and optionally well-founded termination. |
| Parallel composition | Interference/ownership or rely-guarantee conditions and declared observation semantics. |
| Compensation | Explicit subsequent behavior; it does not erase earlier observable effects. |

Capabilities/resources use explicit affine or linear judgments as appropriate.
Ordinary logical assumptions remain reusable; resource hypotheses cannot be
silently duplicated. Check splits and joins, including branch and failure paths.
Mode and determinism declarations constrain relational generation; they are
checked for the supported fragment and do not promise arbitrary Prolog termination.

Freeze the admitted rule environment by digest. Extending it changes the trust
boundary and invalidates incompatible derivations. Keep proof search untrusted,
bounded and replaceable; the checker must work with search disabled.

## 5. One elaborated model, multiple interpretations

Readable model declarations elaborate into canonical typed behavior IR, source
maps, explicit assumptions, obligations and derivation records. Preserve occurrence
identities and binder scopes. Existing `.ops` models require a versioned bridge
that retains their current semantics; new syntax must not reinterpret old files.

The reference interpreter executes this IR in Shen. Environment interaction is
represented by typed requests/responses and explicit choices, not hidden host I/O.
The same IR supports:

1. Simulation: produce successor states, results, effects and transition witnesses.
2. Generation: enumerate or search legal commands and histories, with finite
   domains/modes/budgets and a separately labeled invalid-input campaign mode.
3. Verification: generate contract-composition, invariant and refinement obligations.
4. Abstraction: export finite relations and graphs with explicit abstraction maps.
5. Monitoring: relate implementation observations to allowed histories and retain
   multiple possible model states when observations do not resolve nondeterminism.

Do not independently hand-code five subtly different semantics. Optimized
interpreters, WP compilation and graph abstractions require correspondence
obligations and differential tests; remaining trusted translations stay listed.
Model execution correctness and input generation completeness are different claims.

## 6. Implementation correspondence and port correctness

An adapter needs both an execution interface and a versioned observation mapping.
Map concrete requests, responses, errors, store state, effect journals and event
histories to domain values. Preserve raw records and state exactly which internal
steps are hidden, which observations are normalized, and which events are visible.
An overly coarse map must not hide duplicate charges or observable ordering.

For a chosen environment and scope, safety conformance means every projected
implementation history is allowed by the relevant model. Testing establishes this
only for the exercised histories. General refinement requires a simulation or
other justified correspondence argument over implementation transitions, including
hidden/stuttering transitions where used. Testing the Shen model cannot supply
that argument for arbitrary PHP or Go code.

Trace inclusion alone can admit an implementation that never completes a request.
Add explicit enabledness, supported-operation, response/progress and fairness
obligations where required. Require bidirectional observational equivalence only
where the migration contract actually demands it. Intentional corrections and
allowed implementation nondeterminism usually need more specific relations.

Run the same scenarios against model, legacy implementation and replacement.
Compare each implementation to its own approved model variant, then classify the
cross-implementation difference against the migration contract:

| Finding | Treatment |
| --- | --- |
| Legacy disagrees with its model | Investigate model/extraction/adapter error or previously unknown behavior. |
| Target violates intended behavior | Candidate target defect; preserve and minimize the trace. |
| Legacy and target differ under an approved change | Check the change's replacement obligations; retain both observations. |
| Legacy and target agree but violate intended behavior | Shared defect or incorrect requirement; agreement is not correctness. |
| Mapping or specification is incomplete | Open obligation with affected scope; never auto-approve. |
| Timeout or missing journal | Operational limitation or explicit pending outcome; not semantic success. |

## 7. Evidence loop and auxiliary engines

Use one content-addressed vocabulary: Model, Claim, Obligation, Proposal, Evidence
and Judgment. Each binds exact model variant, migration decision, environment,
assumptions, producer/checker versions and scope. Semantic results and operational
results remain separate; do not compute a confidence scalar from unlike evidence.

Souffle derives finite relations, dependencies, candidate targets and coverage
facts. Preserve the existing Python/interpreted/compiled differential harness.
Negation requires completeness evidence; unresolved calls/edges remain unknown.
Aggregate witnesses can be reconstructed by joining the selected value back to
its source relation, with ties retained and provenance checked.

GraphWalker is an optional path proposer over a declared finite abstraction.
Its model format and installed generator behavior must be verified against a
pinned release before implementation. Export only supported semantics. Guards
on an abstract graph are not general path-feasibility proofs. Validate proposals
against the executable model; solve/generate concrete inputs through supported
Prolog constraints or a separately justified solver. A path with no found inputs
remains open. A generator seed reproduces proposal choices, not host execution.

Prioritize obligations by declared risk, dependencies and missing evidence, then
propose, execute, check and update. A single experiment may cover several claims,
but evidence is admitted separately for each matching scope. `static_only` becoming
`both` describes matched coverage, not a universal semantic correctness proof.

ELF/basic-block extraction remains optional. A program location is not complete
machine state: registers, memory and environmental semantics are needed for
behavioral reasoning. Any binary producer must map artifacts and traces to claims,
record unresolved control flow, and label graph-relative reachability honestly.

## 8. Nondeterminism, concurrency and replay

Distinguish model-permitted alternatives, uncontrollable environmental events and
choices actually forced by the harness. Unknown commit must retain alternative
states until observations resolve it; do not select a convenient outcome branch.
Use actor IDs, invocation/completion intervals, pending operations and causal edges.
Consistency requirements are per operation/store/workflow, not one global promise.

Record artifact/configuration/data identities, inputs, time, entropy, delivery,
retries, process restarts and relevant schedules. Adapter declarations about
control are assertions that need enforcement evidence. Independent store reads
are not automatically a consistent observation cut. Progress claims identify
fairness assumptions. Finite execution success does not prove general liveness.

## 9. Adoption and acceptance

First introduce typed state/commands/effects and checked behavioral composition
alongside existing `.ops` semantics. Then integrate claim admission and
transformation witnesses. Develop production adapters alongside that work.
General induction and concurrency extend the same language rather than creating
parallel modeling systems. The roadmap's R-changes order this work; their
dependencies are kept only in [roadmap-deps.json](roadmap-deps.json).

The first complete integration fixture is an account transfer with an outbox,
idempotent retry and a response-lost outcome. Its legacy variant deliberately
allows a duplicate effect; its intended variant forbids it. Include an approved
migration decision. R10 runs it on model and fake executors: detect the legacy
defect in a history with an indeterminate step, accept the intended difference
only under the decision, and reject a target mutant; conservation there is
bounded per-transition checking. R10q repeats it against real-service adapters
with conservation proved, and the failure replayed and minimized. This fixture
tests the architecture; release scope remains the full inventoried consumer
application.

Acceptance requires adversarial tests for forged contract derivations, omitted
error paths, capability duplication, unsound frames, changed model identities,
normalization that hides effects, unreachable preconditions and missing mapping
coverage. Reuse existing kernels where sound; do not discard passing semantics or
claim full implementation refinement from model-level proofs.

No new runtime is required. Python remains transport/storage/orchestration while
Shen owns model semantics and checked judgments. Optimize only after measuring;
worker isolation and complete dependency identities precede incremental reuse.

## 10. Glossary

**Clause.** An identifiable, versioned behavioral requirement in a legacy model,
intended model or migration contract. Claims, decisions and obligations name
clauses by identity; changing a clause changes its identity and invalidates its
dependents.

**Proposal.** An untrusted candidate experiment or derivation targeting specified
obligations. Proof search, Prolog, Soufflé targeting, GraphWalker, a developer or
an LLM may produce one; none is admitted without checking.

**Critical.** A classification the consumer assigns to a clause or inventory
entry, with a named owner and explicit promotion consequences: an unresolved
critical obligation blocks target admission. capcov does not infer it.

**Evidence policy.** Versioned requirements stating which evidence kinds, scopes,
assumptions and operational controls satisfy an obligation. It has no weighted
confidence score. No evidence-policy artifact exists yet. Existing code has
narrower policy components that an evidence policy may reference, but they are
not that concept. An evidence-policy bundle in `capcov.claims` gives each
evidence relation an explicit polarity toward a claim (`EvidenceMapping` with
support, refutation, observation or forbidden effect, `claims/ir.py`);
`tests/claim_semantics/test_evidence_policy.py` checks that the claim-semantics
corpus compiles into that form and that malformed bundles are refused.
`DerivedCompletenessPolicy` (`claims/contracts.py`) names one
reviewed exact closure rule, by digest, as an admissible way to establish a
relation's completeness; `DiagnosticPolicy` (`claims/ir.py`) declares how a
bundle reports missing or inconsistent premises, out-of-scope and forbidden
evidence, revocation and required completeness. The replay and static
"evidence policy" tests (`test_replay_evidence_policy`,
`test_static_evidence_policy`) check that a claim joining observations from
different producers stays unresolved, naming the missing premise, until the
declared rows and binding witness are present.

**Indeterminate outcome.** A step whose result was not observed: a lost
response, timeout or crash after sending (`info` in `capcov.faults`, as opposed
to `ok` and `fail`). It stays open until the history closes and may take effect
at any later point, including after the final reads. Every admissible
alternative is retained; none is selected for convenience.

**Observation cut.** The declared set of reads (stores, journal ranges, cursors)
from which a history's state and effects are taken, with the barrier that makes
them mutually consistent. Independent reads of several stores are not a cut
until that barrier is established. A missing journal range or unestablished cut
makes the result unresolved, never an empty set of effects.
