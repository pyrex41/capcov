# Behavior integration: completion and follow-up work

The reusable integration in [PR #22](https://github.com/pyrex41/capcov/pull/22)
is implemented. Its validation record remains narrower than production
qualification. The upstream runtime now builds on Linux x64, and the integrated
finite protocol and observed-history checks pass without replacing the
authoritative checker.

This document maps outstanding work to the existing
[production roadmap](production-roadmap.md) and its authoritative
[dependency registry](roadmap-deps.json). It does not create a second roadmap
or mark the R-series complete. “Owner” below names a responsible component or
repository, not an assignment to an individual.

## Current integration

| Piece | Current result |
| --- | --- |
| Behavior registry, store layers, access paths, source invalidation | Implemented and exercised by regression tests |
| Recovery import and priority work list | Implemented; static claims remain static |
| Shen Step handlers and worker effect restrictions | Implemented for the documented closed fragment |
| Stateful adapter, effect replay, exact migration decisions | Implemented with the synthetic publication example |
| Soufflé evidence impact | Uses existing rules; native agreement test passes |
| ShenCheck/Vör integration | One mandatory engine check in the same gate; sources, controls, history and artifacts are bound |
| Shared protocol execution in this environment | FINITE_PROTOCOL_VALIDATED: all controls and observed history pass on upstream 8d26151 |
| Documentation | Method, Reversa comparison, capcov comparison, synthesis, example and validation record are included |

## Follow-up acceptance criteria

| Existing work item | Owner | Concrete next work | Completion evidence |
| --- | --- | --- | --- |
| R01 — pinned baseline | Shen-Scheme runtime/build and capcov validation | Linux x64 runtime and integrated lane resolved; verify Nix and remaining supported platforms | Retained source/runtime identity; healthy result plus all four required defect controls and the concrete observation check; no UNKNOWN substitution |
| R22 — release qualification | capcov CI/package maintenance | Run the full pinned Nix/Earthly checks against the feature revision; diagnose the broad unpinned-suite failures separately | Complete skip-accounted results, installed-package checks and current revision-bound logs |
| R02, R04, R06 — typed language and contracts | capcov semantic kernel | Relate the small Step fragment to the existing behavior IR and checked contract judgments before advertising richer domain typing | Explicit bridge/correspondence obligations, positive and negative admission cases, and checked domain derivations; phase admission alone is insufficient |
| R07, R15, R16 — generation and replay | capcov with ShenCheck/Vör | When broader campaign generation/shrinking is needed, consume it through the same obligations and gate | Deterministic retained scenarios, bound counterexamples, replay/shrink checks and rejection of incomplete campaigns; no standalone verdict to reconcile |
| R09, R14 — real adapters and observation | Consuming application | Implement and characterize SQL, cache, document-store and queue access paths, codecs, tenant selection and coherent observation boundaries | Corpus-backed adapter laws, malformed/sentinel cases, authorization and isolation tests, and mixed-writer tests against actual stores |
| R17 — worker protocols and refinement | Consuming application with Vör/ShenCheck | Extend concrete observation beyond the current commit/response prefix to worker ownership, retries, acknowledgement and settlement | Observed histories under the same model, explicit fencing/provider assumptions, crash and duplicate-delivery controls; model safety remains distinct from implementation refinement |
| R19 — application rollout | Consuming application | Inventory all entry points, identify user-relied-on behaviors, classify uncovered routes and resolve preservation/change decisions | Per-entry corpus/context coverage, reviewed representation decisions, prioritized vertical cutover units and retained coexistence/rollback evidence |

General protocol proofs, liveness, implementation refinement and translation
proofs remain the separate OPEN claims reported by the existing ShenCheck/Vör
lane. A finite run cannot close them. Only require those stronger obligations
where the advertised scope or consumer contract calls for them; never present
the synthetic fixture as proof of a production system.

The next release verification is the full pinned Nix/Earthly gate, including
the existing `capcov behavior check` command on supported platforms. There is no second checker workflow to select
or manually merge. `behavior gate` continues to reject absent, stale, failed or
unknown evidence.
