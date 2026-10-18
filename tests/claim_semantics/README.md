# Stage A claim-semantics corpus

The numbered JSON files are evaluator-independent semantic controls.  A
reviewer can inspect `claims`, `facts`, `assumptions`, and `expected` without
running Python, Soufflé, Shen, or the capcov claim package.

Each fixture references `corpus/schema-v1.json`, which fixes ordered typed
relation arguments, context indices, polarity, and modality. Every claim,
fact, and assumption carries its ordered `args`, complete context-key map, and
explicit provenance dependencies.

Each per-claim expected result keeps five things separate:

* `semantic_verdict`: `supported`, `refuted`, `unresolved`, or `conflicting`;
* `operational_status`: one of the canonical claims statuses (`complete`,
  `invalid-input`, `inconsistent-premises`, `resource-exhausted`,
  `unsupported-construct`, `stale`, or `out-of-scope`);
* `support_leaves` and `refutation_leaves`: polarity-specific derivation IDs;
* `observed_leaves` and `forbidden_leaves`: all observed inputs versus IDs a
  derivation must not use;
* `discrepancies` and `missing_premises`: why a tempting Boolean answer is not
  sufficient.

`expected.json` is a review table duplicated from each fixture.  The tests
only validate that the table and fixtures agree; they do not evaluate rules.
The fixtures are synthetic controls until a real retained execution is added.
`adapter.py` converts each fixture to strict bundle JSON and invokes the real
`bundle_from_json(..., validate=True)` parser; it does not evaluate rules.

## Checker authority is operation scoped

The typed checker emits two producer facts. `model_well_formed.json` records
global model structure. `model_operation_checked.json` records a positive row
only for each operation whose local write, matrix, atlas, and registry
judgements all pass. A skipped or failing operation has no row and cannot
borrow another operation's result. The modelcheck certificate digest includes
stable semantic inputs and judgements; it excludes nonce, elapsed time, and
other run-envelope values. Its `checker_binary` is the SHA-256 of the resolved
native Shen executable. The Bifrost launcher hash remains a separate input to
the semantic certificate.

Reviewer authority is supplied separately to the exporter. Each
`model_checker_admitted` row must match the model, operation, checker name,
version, native binary digest, and semantic certificate digest of one exact
`model_operation_checked` row. Receipt-local `model_checkers.json` is ignored,
and placeholder reviewer names contribute no authority. Structural validity,
operation coverage, and reviewer admission remain positive premises with no
closure relation.

A receipt from a real system with no checker observations or caller
admissions remains pending at the first missing checker-authority premise;
such receipts stay with the system that produced them and none is committed
here. That is distinct from a finding against the port:
the checker premises stay last in `_BLOCKING_ORDER`, the summary reports
`pending <premise>`, and `scripts/compiled_checker.py` exits **5** when every
required operation reaches only a pending checker premise. Exit **1** wins
when an operation has a real blocker such as `undeclared_any`.

`replay_receipt_min` and the corpus derived from it remain explicitly
synthetic. Their made-up structural, operation, and reviewer rows exercise the
positive join. Corpus case `32-partial-operation-check` has checker authority
for `delete-issue` only; the other operations stay pending at
`model_operation_checked`.

## Assumption registry and invalidation

`capcov.claims.assumptions` gives each reviewed assumption a run-independent
`asm:` id (producer class + relation + row, so one reviewed row keeps one id
across runs), registers what each assumption carries, and withdraws one —
dropping an assumption and re-evaluating both kernels to see which claims lose
support. `test_claims_assumptions_cli.py` drives it over `replay_receipt_min`
from the command line:

```
capcov experiment claims assumptions registry   --receipt DIR [--out DIR]
capcov experiment claims assumptions invalidate --receipt DIR --drop ID
```

`--receipt` falls back to `CAPCOV_REPLAY_RECEIPT_DIR`; with neither the command
refuses. Exit 0 when the documents were produced, 2 for a refusal (an unknown id, or a
withdrawal that would refute a claim rather than leave a premise missing), 3
when the kernels disagree. Needs Soufflé, no replay environment.

### Specification migration work in progress

`specs/claims/` contains readable typed declarations and named logic rules for
all 154 pack rules and the two shared bridges. Replay, static, observation and
the shared bridges all use Bundle v2 and native closure elaboration.
`baseline-v1.json` pins the compatibility identities and unchanged `model_min`
fixture. All installed defaults remain v1; replay, static and observation v2
profiles are selectable. The preserved-behavior and
authority-tightening reports record the remaining work.

The compiler requires the pinned native Shen runtime:

```sh
nix develop .#shen --command capcov experiment claims spec build \
  --source specs/claims/replay.claims --out /tmp/replay-spec
nix develop .#shen --command capcov experiment claims spec check \
  --source specs/claims/replay.claims --artifacts /tmp/replay-spec
```

From an uninstalled checkout, use `env PYTHONPATH=src python -m capcov` instead
of `capcov`. `compile_spec(source, timeout=60)` returns data without writing;
`check_spec(source, artifacts)` recompiles and reports missing, changed, and
unexpected artifacts without updating the directory. The manifest binds the
import closure, compiler sources, Python/native runtime identities, and output
digests. It omits timestamps and absolute paths. Missing Shen is an operational
failure. Installed pack evaluation reads JSON and does not require Shen.

Authored sources use `.claims 2.` followed by typed relation declarations and named
Datalog rules. For example, replay now contains:

```text
.completes model_writes_closed -> model_writes by model=model, op=op.

undeclared_write_php: undeclared_write(Run, Op, Tb) :-
    replay_request(Run, Req, Tenant, Route, Op),
    php_effect(Run, Req, Tb, Kind, Pk, Cols), model_describes_run(M, Run),
    !model_writes(M, Op, Tb), model_scope_exclusions_closed(M),
    !model_scope_excluded(M, Tb).
```

Native Shen inserts the two required closure premises. The independent Python
checker reconstructs their exact terms, order, and source obligations. A
compiler obligation never creates a closure fact. Replay declares 37 scopes
and removes 24 redundant premises; its 71 elaborated rules equal the frozen v1
rules exactly. Remaining closure premises express stronger gates, explicit
closure policies, or bind an absence claim's domain. Observation declares 28
scopes and 14 named exact-rule closure policies, and removes 21 premises --
every closure that immediately guarded a negation; its 56 elaborated rules
equal the frozen v1 rules exactly, in their original premise order. It declares
no `.capability` or `.bridge`: every observation relation is runtime-bound and
the pack is model-free, so a compatibility relation there would be ceremony.

Static declares 7 scopes (in `static-relations.claims`, shared with the
bridges) and 1 named closure policy (`static_route_authorized_closed`); native
Shen regenerates 3 premises (`static_file_unindexed`,
`runtime_route_without_static`, `static_route_authorization_gap`) and the 27
elaborated rules equal the frozen v1 rules exactly, with digest `c11d6289…`
reconstructed. `index_describes_run` is now an unscoped v2 witness with one
directional capability (`scip_index` and `static_route_declared_surface` to the
runtime route and trace primitives) and the `index-run` bridge. The two shared
bridges regenerate no premises and equal the frozen
`runtime-shared-v1.json` rules; that v1 bundle is now frozen generated data
rather than recompiled from `shared.claims`.

`.decl` marks context columns with `ctx`; `.capability` names directional
endpoints; `.bridge` requires a dimension association; `.policy` binds a reviewed
closure rule. Constants use JSON strings or integers with optional `::type`;
variables begin with uppercase letters. `_` introduces a fresh variable.
Negated variables must already be positively bound. Imports are literal paths
relative to the entry source's directory. Escapes, cycles, executable forms,
and unsupported syntax are rejected. The old bracketed data reader remains
available for compatibility fixtures. Operations are not yet implemented.

`.template side(Side) { rule ... }` and `.instantiate side(php).` expand rules
once at decode, before elaboration; no kernel sees a template. `$Side` inside
a rule or relation name substitutes the argument text, and a whole term
`$Side::symbol` becomes `"php"::symbol`; variables and strings never change.
Expanded rules are emitted at the instantiation, which is order-safe because
Bundle rules are a canonically sorted set. Templates hold rules only, cannot
instantiate one another and must be defined before use. Unbound parameters,
arity mismatches, unknown templates and name collisions are named refusals.
Native Shen (`shen/spec-templates.shen`) re-expands the raw template data and
compilation refuses on any difference; `obligations.json` and the source map
trace each expanded rule to its template rule and instantiation. Replay's
13 php/go families are one template; `spec_fixtures/replay-pretemplate.claims`
is the untemplated oracle it must decode identically to.

Bundle v2 adds explicit directional capability endpoints, required bridges,
complete closure-column maps, and named derived-completeness policies bound to
exact rule identities. Complex policies retain their explicitly authored
premises, including the learn reporting gate; absence of a reported downgrade
is not comprehensive coverage. Scoped compatibility witnesses currently fail
construction checking rather than silently ignoring their scope. V1 canonical serialization omits all v2 fields.
`convert_v1` requires explicit contracts and returns the old and new identities;
it never converts certificates. Combining versions or conflicting contracts
fails. V2 mapping admission, aggregation closure, and universal-domain
admission are explicitly unsupported pending their independent checks.

`test_authority_v2.py` gives the same authored corpus independently to Python
and Shen. Native tests call `authority(..., validate=False)` and retain native
diagnostic identifiers. `test_v2_certificates.py` covers mutated obligations
and evaluation bases. `recheck(...).ok` means structural validity;
`fully_checked` additionally requires no unchecked obligations. V2 promotion
requires an independently recomputed complete evaluation basis. This does not
prove external-world completeness or replace producer admission. Native v2
certificate generation is deliberately refused until its versioned basis
protocol is implemented.

The three native/Python disagreements are resolved: `learn_consistent` is a
scoped absence claim; `model_scope_excluded` and `masked_admitted` are single
assumption projections. Direct assumption-to-claim promotion still fails, as
does laundering the assumption through a derived projection before the claim.
Native tests are registered in the Shen CI family, which requires the runtime.

Select replay v2 with `replay.join.build(..., version=2)` or
`capcov experiment claims assumptions registry --receipt DIR --pack-version 2`.
The immutable profile travels through export, combination, and evaluation.
Installed v2 pack/schema/stub bytes are checked against their generated
manifest. V1 remains the default and retains its canonical identities.
`test_replay_spec.py` compares all 28 frozen cases and individual closure and
assumption withdrawals, checks the receipt-to-certificate path, and compares
Python, interpreted Souffle, and compiled Souffle. The installed-wheel test
loads both replay and both observation versions without repository files or Shen.

Select observation v2 with `observation.join.build(..., version=2)` or
`python -m capcov.claims.observation.judge ... --pack-version 2`; a v2 judge
report adds `pack_profile`, and v1 reports keep their exact shape. The
exporter's rows, evidence ids and observation identity are computed over the
frozen primitive schema under either profile. `test_observation_spec.py`
compares the four committed receipts (agree, disagree, gap, masked) and the
admitted-mask control under v1 and v2, including every individual closure and
assumption withdrawal, checks v2 certificates against an evaluation basis,
compares the judge CLI decision under both profiles, and runs all three
kernels on v2. `test_spec_compiler.py` reconstructs the frozen observation
rules from the native elaboration and checks each of the 21 insertions.

Select static v2 with `static.pack.pack_bundle(version=2)` and
`scip_facts.export_bundle(..., pack_profile=resolve_profile('static', 2))`
(also `export_from_tree`). A v2 export carries the pack's exact declarations
and contracts; its index identity is unchanged from v1. `test_static_spec.py`
compares all 14 frozen static cases and individual closure and assumption
withdrawals, checks the go_app export-to-certificate path, and compares
Python, interpreted Souffle, and compiled Souffle. Claims are excluded there
because v2 universal-domain admission is pending.

The operation framework, Shen datatype judgments and Prolog search, templates,
declarative reporting policy, the static pack migration, and full release gates
are still outstanding. This milestone demonstrates real replay and observation closure
elaboration; it does not claim the complete original architecture is delivered.

### Typed operation milestone

See [operation specifications](../../docs/operation-specifications.md) for the
new native Shen instruction kernel, sequent construction judgments, one-source
delete-issue example, explicit deployed divergence, Prolog observation/search,
and independent transition corpus. This is an opt-in experimental API; it does
not promote operation outputs into completeness or reviewer-admission facts.

The compositional system suite (`test_systems.py`) covers workspace CRUD and
authorization, ledger transfers/idempotency/conservation, and split outbox
workflows. See [System specifications](../../docs/system-specifications.md)
for the native language, harness, campaign and claim-export interfaces.

## R10 probe: outbox migration on the current system IR

`test_migration_probe.py` is a worked migration model, not a qualification.
Legacy model `fixtures/systems/outbox.ops`; intended model
`fixtures/systems/outbox-intended.ops` (send is idempotent per job: a second
send of an `attempted` job publishes nothing); decision record
`fixtures/systems/outbox-migration-decision.json`. The decision record is a
fixture for this probe only and **not a schema commitment**; its approver is a
placeholder with no reviewer authority.

Every result names its executor class: `model` (the Shen system evaluator) or
`fake` (`scenario-adapter.py`, a synthetic stand-in, never a legacy
implementation). Model results also record `depth` and
`basis: explicit-bounded-domain`; fake results record
`basis: fake-observation`. Outcomes use the `capcov.faults` vocabulary
(`ok`/`fail`/`info`); `info` is the IR's `unknown`. Verdicts are `satisfied`,
`violated` (with the faults invariant `effect_applied_twice` or
`unsettled_effect`) or `unresolved`: a clause over zero complete histories is
`unresolved`, never `satisfied`, and paths that end early (an inadmissible
transition, or explore stopping when its frontier empties) are counted as
`truncated`, not dropped.

A difference is `accepted` only when the decision is approved and bound to
both clause ids and both models, and the legacy, target and guard-dropped
mutant evidence each come from a `model` executor, evaluate the intended
clause on the model the decision names, carry a scope digest of the explored
initial state and schedule equal to the decision's, and have at least one
complete and no truncated history. The obligation checks are computed from
that evidence. A target that violates the intended clause is `rejected`, and
agreement with legacy on that violation is reported.

Delivery attempts are counted by intent id when an effect carries one, and
otherwise by payload, labelled `payload-fallback`; the current IR always
takes the fallback.

The ledger case is the transfer postcondition (sum of balances unchanged,
`ledger.ops:23`) checked per transition over an explicit finite domain; a
failure is reported by `caps.finish` as `["rejected", "invariant"]`
(`system.shen:141-145`). It is a bounded invariant check, not a conservation
proof; the proof is R12.

Families: `MigrationDecisionRecordTests`, `FakeExecutorTests` and
`InexpressibleFrontEndTests` run in `base`; `MigrationProbeModelTests` and
`InexpressibleModelTests` need Shen and are in the `shen` family.

### Expressible today

| Case | Test | Executor | Result |
|---|---|---|---|
| Legacy explores to duplicate delivery-attempt (`send ok; send ok; ack ok`) | `test_legacy_explores_to_duplicate_delivery_attempt` | model | `effect_applied_twice` |
| Intended does not deliver twice, in explore and in the observation checker | `test_intended_does_not_deliver_twice`, `test_intended_checker_refuses_observed_double_delivery` | model | satisfied; observed double delivery refused |
| Difference accepted only with an approved, bound decision and covering evidence | `test_difference_accepted_only_with_an_approved_decision` | model | accepted / open |
| M5: decision with missing approval provenance | same, and `test_m5_missing_approval_provenance_keeps_the_decision_open` | model / none | open |
| Evidence not bound to the decision: wrong clause, fake as legacy, other schedule, mutant not killed | `test_wrong_clause_is_not_accepted`, `test_fake_as_legacy_is_not_accepted`, `test_scope_mismatch_from_a_different_schedule_stays_open`, `test_obligation_is_computed_from_evidence` | model, fake | open |
| No vacuous pass: a target that rejects the retry | `test_target_that_rejects_the_retry_is_not_accepted`, `test_no_complete_history_is_unresolved_not_satisfied` | model | open; `unresolved` |
| Guard-dropping target mutant; legacy and target agreeing on a violation is still reported | `test_guard_dropping_target_mutant_is_rejected` | model | rejected |
| M1 double delivery on `ok` | `test_m1_fake_double_delivery_on_ok_violates_the_intended_clause`, `test_m1_fake_double_delivery_is_rejected_by_the_legacy_model` | fake, model | rejected |
| H1 `send info; send ok; ack ok`, truth 2 deliveries | `test_h1_info_then_ok_retry_two_deliveries`, `test_h1_truth_two_deliveries_from_the_fake` | model, fake | legacy finding; intended violation |
| H2 same calls, truth 1 delivery; both info resolutions retained | `test_h2_info_then_ok_retry_one_delivery_keeps_alternatives` | model | pass |
| H5 same idempotency key, different amount | `test_h5_same_idempotency_key_different_amount_conflicts_without_debit` | model | `idempotency-conflict`, no debit |
| M2 payload dedupe drops a delivery (count falls) | `test_m2_payload_dedupe_leaves_an_unsettled_effect` | model | `unsettled_effect` |
| M3 `ok` reported for an `info` send that did not land | `test_m3_reporting_ok_for_an_info_send_is_rejected` | model | rejected |
| Harness negative: different `info` resolution is a different history, never a replay | `test_harness_negative_*` (both classes) | fake, model | distinct history ids |
| Ledger transfer postcondition, bounded per transition | `test_ledger_transfer_postcondition_is_a_bounded_per_transition_invariant_check` | model | no invariant violation within bound; mutant caught |

All of these rest on the atomic-publish assumption of the current IR: a
`publish` commits with its transaction (`system.shen:67`), so an `info` send
has exactly two alternatives (`system.shen:165-166`).

### Not expressible today (IR-gap tests)

This table is the input to the IR specification. Each IR-gap test is a
`unittest.expectedFailure` method whose expressible precondition runs in
`setUp` (a `given_*` method), so a broken precondition, such as a typecheck
failure, is a normal failure and cannot pass for the documented gap; only the
gap assertion is expected to fail, and an `OperationError` there becomes a
failure naming the gap. Each row flips to an unexpected success, which fails
the run, when its "flips when" condition holds. The front-end rows prescribe
one possible wire shape (a `journal` field, a fourth effect element,
`outbox`/`deliver` tags); the IR specification may choose another, and those
tests change with it.

| Case | Test | Missing IR feature | Where the IR stops | Flips when |
|---|---|---|---|---|
| `info` send admits nothing / outbox-only / outbox+delivered | `test_info_send_has_at_least_three_alternatives` | an `info` outcome with more than two alternatives; an outbox-recorded-not-delivered state | `system.shen:165-166`; binary tape `scenarios.py:56-57`, `adapters.py:63-64` | the intended model's info send explores to ≥3 alternatives |
| H3 delivery lands after the final read ⇒ `unresolved` | `test_h3_delivery_after_final_read_is_unresolved` | `info` invocations open until history close; a final-read / close marker | unknown resolved in its own transition `system.shen:165-166`, `scenarios.py:125-126`; no open set in `explore` `system.py:451-466`; request fields `system.py:110-118`, outcomes `system.py:126-128` | the info step's `observed_matches` is not `True` before close |
| H4 missing journal range ⇒ `unresolved` | `test_h4_missing_journal_range_is_unresolved` | partial observation (journal gaps, unestablished observation cut) | observation is exactly `{state, effects}` `system.py:132`, `scenarios.py:100`; whole-list match `system.shen:168-169` | `_request` accepts an observation with a journal gap |
| Intent / attempt identity on effects (**flipped by R02 PR 1**, no longer an expected failure) | `test_effects_carry_intent_and_attempt_identity` | `(intent-id, attempt-id, logical-effect)` effects | was: fixed-arity effects; now the record `[effect I A L]` (`docs/ir-specification.md` 4.2) | `_effect_terms` accepts `["effect", "j", "i1/publish", ["emit", ...]]` |
| Outbox record vs delivery attempt | `test_outbox_record_and_delivery_attempt_are_separate_constructors` | separate transactional outbox-record and external delivery-attempt constructors | single `publish` `system-types.shen:59-61`, `system.shen:67`; tag whitelist `system.py:24-26` | the front end accepts the two constructors |
| M2 dedupe by intent, not payload | `test_m2_delivery_effects_carry_intent_identity` | intent identity on emitted effects | two jobs with one payload emit identical effects (`system.py:100-104`, `system.shen:67`); `at_most_once` takes the payload fallback | the intended model's two delivery effects differ by intent id (then `at_most_once` counts per intent) |
| M4 adapter normalizes effects to a set | `test_m4_adapter_that_normalizes_effects_to_a_set_is_rejected` | journal positions (both landings are one attempt, so attempt identity does not separate them; spec 4.5 O4) | equal tuples collapse (`system.py:100-104`); `caps.accepts?` `system.shen:168-169` | the set-normalized report of the double delivery mismatches |

Deferred to qualification, explicitly: conservation proof (R12), controlled
replay (R15), causal minimization (R16).
