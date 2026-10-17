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
all 154 pack rules and the two shared bridges. Replay, static, and the shared
bridges use Bundle v2 and native closure elaboration; observation retains v1.
`baseline-v1.json` pins the compatibility identities and unchanged `model_min`
fixture. All installed defaults remain v1; replay v2 and static v2 are
selectable. The preserved-behavior and
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
closure policies, or bind an absence claim's domain.

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
available for compatibility fixtures. Templates and operations are not yet
implemented.

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
loads both replay versions without repository files or Shen.

Select static v2 with `static.pack.pack_bundle(version=2)` and
`scip_facts.export_bundle(..., pack_profile=resolve_profile('static', 2))`
(also `export_from_tree`). A v2 export carries the pack's exact declarations
and contracts; its index identity is unchanged from v1. `test_static_spec.py`
compares all 14 frozen static cases and individual closure and assumption
withdrawals, checks the go_app export-to-certificate path, and compares
Python, interpreted Souffle, and compiled Souffle. Claims are excluded there
because v2 universal-domain admission is pending.

The operation framework, Shen datatype judgments and Prolog search, templates,
declarative reporting policy, remaining pack migrations, and full release gates
are still outstanding. This milestone demonstrates real replay closure
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
