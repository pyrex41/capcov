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

`specs/claims/` contains restricted bracketed data declarations for all 154
frozen v1 pack rules and the two shared static/runtime bridge rules.
`baseline-v1.json` pins the existing canonical Bundle identities and the
unchanged `model_min` fixture. This is a baseline transcription, **not a
completed migration of the three packs to v2**. Installed profiles still use
v1. The preserved-behavior and authority-tightening reports in that directory
record the current boundaries and remaining work.

The compiler requires the pinned native Shen runtime:

```sh
nix develop .#shen --command capcov experiment claims spec build \
  --source specs/claims/static.claims --out /tmp/static-spec
nix develop .#shen --command capcov experiment claims spec check \
  --source specs/claims/static.claims --artifacts /tmp/static-spec
```

From an uninstalled checkout, use `env PYTHONPATH=src python -m capcov` instead
of `capcov`. `compile_spec(source, timeout=60)` returns data without writing;
`check_spec(source, artifacts)` recompiles and reports missing, changed, and
unexpected artifacts without updating the directory. The manifest binds the
import closure, compiler sources, Python/native runtime identities, and output
digests. It omits timestamps and absolute paths. Missing Shen is an operational
failure. Installed pack evaluation reads JSON and does not require Shen.

Sources have one `[claims-spec 1 ...]` form. Declarations include `pack`,
`primitive`, `supplementary-primitive`, `derived`, `rule`, `capability`,
`required-bridge`, `completeness-scope`, and `derived-completeness-policy`.
Payloads are `[object [field value] ...]` records and `[array ...]` arrays;
strings use JSON quoting. Imports are literal paths relative to the entry
source's directory; escaping that root, cycles, executable forms, and unknown
constructs are rejected. Templates and operation declarations are not yet
implemented. V2 closure insertion runs in Shen and is reconstructed
independently in Python; generated obligations never create closure facts.

Bundle v2 adds explicit directional capability endpoints, required bridges,
complete closure-column maps, and named derived-completeness policies bound to
exact rule identities. A derived closure policy must retain a positive
completeness premise. V1 canonical serialization omits all v2 fields.
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

Current compilation exposes three pre-existing native/Python authority
mismatches: replay's `learn_consistent` and `model_scope_excluded`, and
observation's `masked_admitted`, fail native `declaration-promoted-to-effect`.
The compiler reports these failures; it does not waive them. The static pack
and shared bridges compile. Resolving these rule-purpose declarations is a
release prerequisite, alongside the remaining operation framework, templates,
profile migration, Prolog search, reporting metadata, and complete release CI.
