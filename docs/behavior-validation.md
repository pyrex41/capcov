# Behavior integration validation

The feature starts at fork `64d6ad9729a21ab1520219aee6970e51895a0a68`, which
already includes upstream `1130bc00439e99959aff562e12725e8fb438e8ac`.

Final focused results: **31 new tests passed, zero skips**, through the example's
own check plan (11 native target/adapter tests and 20 receipt/integration/graph
tests). Ten existing CLI/source-evidence tests also passed without skips.
ShenCheck's external model/translation suite passed 22 tests. The integrated
cutover-policy report remains incomplete with exactly `protocol-safety`
unresolved; the real ShenCheck process returned exit 3 / UNKNOWN.

Validation is reported per mechanism. This file is a work record, not an engine
receipt or a certificate for a production application.

- Native Step, SQLite adapter and effect replay tests ran through Bifrost and a
  Shen-Scheme 0.52 / Chez 10.3.0 host. This host is not the exact fork release pin.
- Registry, receipt, decision-scope and ShenCheck admission-control tests run
  without native dependencies. Native Souffle 2.5 checks the exported invalidation
  graph against the registry's transitive result.
- The wheel builds and its console entry points start. Ruff checks the repository.
- ShenCheck's pinned model/translation test module was run from the external
  source snapshot; it is not vendored into this public repository.

The current live ShenCheck/Vör qualification is **unresolved** in this environment.
Building the pinned Shen-Scheme v0.52-pyrex41.5 source archive fails Chez's own
bootstrap fixpoint comparison (`sharing1`, fasl entry 297). Two fresh builds
reproduced the failure. The bridge preserves that infrastructure failure rather
than recording protocol qualification under the available alternate host.

During development, a separate handwritten TLA+ publication model passed its
bounded checks. It was subsequently removed in favor of the existing authoritative
Vör -> ShenCheck -> generated-TLA+ lane. Those earlier results do not qualify the
current lane and are intentionally not used by its gate.

The complete pinned Nix/Earthly gate has not run here. The broad unpinned base
suite also encountered failures and slow-running classes; its result must not be
reported as a clean regression run. A fully equipped runner must execute the
normal repository gate and the example's integrated check plan before this branch
is treated as ready for production use.
