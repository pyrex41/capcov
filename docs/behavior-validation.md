# Behavior integration validation

The feature starts at fork `64d6ad9729a21ab1520219aee6970e51895a0a68`, which
already includes upstream `1130bc00439e99959aff562e12725e8fb438e8ac`.

Final focused results: **31 new tests passed, zero skips**, through the example's
own check plan (11 native target/adapter tests and 20 receipt/integration/graph
tests). Ten existing CLI/source-evidence tests also passed without skips.
ShenCheck's external model/translation suite passed 22 tests. The integrated
cutover-policy report now passes all ten obligations with no invalid evidence.
The authoritative ShenCheck/Vör/TLC lane reports `FINITE_PROTOCOL_VALIDATED`,
including all four required defect controls and the concrete observed history.

Validation is reported per mechanism. This file is a work record, not an engine
receipt or a certificate for a production application.

- Native Step, SQLite adapter and effect replay tests ran through Bifrost and a
  freshly built upstream Shen-Scheme `8d26151` / Chez 10.3.0 host, with the
  separately pinned upstream kernel `ec16a9f`.
- Registry, receipt, decision-scope and ShenCheck admission-control tests run
  without native dependencies. Native Souffle 2.5 checks the exported invalidation
  graph against the registry's transitive result.
- The wheel builds and its console entry points start. Ruff checks the repository.
- ShenCheck's pinned model/translation test module was run from the external
  source snapshot; it is not vendored into this public repository.

## Upstream runtime qualification (2026-10-28)

The old fork archive failed Chez's bootstrap fixed-point comparison (`sharing1`,
fasl entry 297). The replacement pins upstream `tizoc/shen-scheme`
`8d261518db17fbfec32d1b268b40ed216b925c74` and compiles its current sources with
checksum-verified upstream v0.52's embedded Chez compiler. It does not bypass
the failed comparison. See [runtime build details](shen-runtime-choice.md).
Vör's integration pin is `a197db255f531987d07b1290cf82fc1242911c16`
([dependency PR #18](https://github.com/pyrex41/vor/pull/18)).

On Linux x64:

- Fresh upstream runtime compilation and Unicode smoke check pass.
- Upstream byte-string and string-boundary suites pass.
- Vör: **76,900 checks pass**, plus the dedicated **11 effects controls**.
- Capcov runtime selection, numeric and text contracts: **14 tests, zero skips**.
- Publication check plan: **31 tests, zero skips**; healthy TLC/reference
  agreement, four matching defect counterexamples, and the observed two-step
  commit/response history all pass in the same gate.

The first full run rejected a retained log with a digest mismatch. A fresh
run passed without relaxing artifact checks; the failed receipt is not used.
The checked scope includes the Nix runtime pin and offline build recipe, and
Vör's exported manifest includes its bootstrap and build recipes.

The kernel and host retain separate identities. Model checking establishes
finite model safety and trace conformance only; the lane still reports general
proof, liveness, refinement and translation proof as OPEN.

During development, a separate handwritten TLA+ publication model passed its
bounded checks. It was subsequently removed in favor of the existing authoritative
Vör -> ShenCheck -> generated-TLA+ lane. Those earlier results do not qualify the
current lane and are intentionally not used by its gate.

## Full Nix regression validation (2026-10-31)

[The revision-bound report](validation/268fa67.md) records the full x86_64-linux
Nix CI run after correcting the upstream archive filename and extraction
ownership. All flake checks, all test families, the control scripts, lint and
package checks pass. The six shard records account for all 2,267 discovered
tests exactly once; the one existing external-model skip is accepted.

The earlier unpinned/local runs were not clean and are not used to establish
this result. Native ARM/macOS execution and Earthly container execution remain
separate validation work. The external ShenCheck/Vör protocol result above
was obtained at its recorded revision and is not newly rerun by this CI suite.

Implementation completion and remaining production work are mapped in
[the follow-up record](behavior-follow-ups.md).
