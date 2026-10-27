# Direct comparison with capcov before this branch

There are two baselines. Conflating them would incorrectly credit this branch
with work already present in the fork.

- Upstream: [`millstonehq/capcov@1130bc0`](https://github.com/millstonehq/capcov/tree/1130bc00439e99959aff562e12725e8fb438e8ac).
- Fork before this work: [`pyrex41/capcov@64d6ad9`](https://github.com/pyrex41/capcov/tree/64d6ad9729a21ab1520219aee6970e51895a0a68).

The fork already contained upstream's complete history at branch creation: 99
commits ahead, zero behind. No reset, history rewrite or duplicate merge was
needed. The feature branch starts from the fork baseline.

## What was already there

Upstream capcov discovers capabilities and reconciles them with observed
execution, including gap reporting and exemptions. Its surrounding tooling
includes source mapping, recordings/vectors and claims-oriented checks. It is
not merely a line-coverage counter.

The fork already extends that foundation substantially: executable `.ops` system
models in Shen; typed authority and contract derivations; native runtime identity;
source anchors and evidence invalidation; Souffle evaluation; Prolog scenario
generation; stateful adapter execution; replay and counterexample minimization;
and the `capcov reason` workbench. The typed-behavior architecture and production
roadmap also predate this branch. Their complete designs are not all implemented.

## What this branch adds

| Addition | Concrete implementation | Reused foundation |
| --- | --- | --- |
| Behavior index | `behaviors/registry.py`: strict versioned registry, dependency closure, priority, source hashes | Existing canonical digest and consumer-owned source artifacts |
| Store/access contracts | Four nonempty store layers; path-specific hooks, scopes and bypasses; shared-writer scope | Existing source inventories and application-owned models |
| Recovery exchange | `behaviors/recovery.py`: claim/gap import that preserves static evidence kind | Existing extraction and provenance concepts |
| Work planning | Priority-sorted unresolved obligations and blocker report | Existing check/proof mechanisms remain the executors |
| Qualification | `behaviors/qualification.py`: reviewed check plan, fresh executions, log/input binding, scoped gate | Existing bounded subprocess runner and exact evidence discipline |
| Migration decisions | Exact scenario/path/value comparison with approved replacement obligations | Existing distinction between legacy, intended and migration contracts |
| Executable target | `behavior-step.shen` and `behaviors/target.py`: closed Step admission, interpretation and correlated sessions | Existing Shen/Bifrost transport and runtime/library hashes |
| Effect replay | Transcript export and request-checked replay without adapters | Existing record/replay approach; existing vector format is unchanged |
| Queryable impact | `behavior graph` exports facts and ID map | Existing `operations/evidence.dl`, rather than a second Datalog evaluator |
| Vertical example | Synthetic publication route, worker and SQLite adapter | Existing `.ops` engine also runs its small legacy abstraction |
| Protocol evidence | Mandatory ShenCheck/Vör cohort, generated TLA+, counterexamples and observed-prefix checking in the same gate | Pinned existing effects lane; no duplicate protocol checker |
| User-facing workflow | `capcov behavior` command family and four connected documents | Existing commands retain their interfaces |

All additions are additive. Existing `capcov gate`, claims verdicts, `.ops`
semantics, vector formats and workbench artifacts are not reinterpreted. The new
registry is an index over consumer artifacts, not a replacement claims database.
The new receipt envelope describes execution of a reviewed check command; it does
not silently inherit the stronger semantics of a capcov model-proof certificate.

## What changes for a migration team

Before this branch, a team could run discovery, model checks, replay and proofs,
but had to assemble store-access obligations, target execution and cutover
coverage in its own workflow. The new surface binds those pieces to a selected
Behavior and refuses a complete result if an enrolled requirement is unresolved.

A passing model proof still proves its model statement. A passing replay still
covers its corpus. A Step admission still checks only its declared fragment.
The registry makes those separate obligations visible together. It deliberately
does not average them into an overall correctness score.

The most consequential dependency rule concerns coexistence: all enrolled writers
of a selected store enter the scope. A source change in an old writer can therefore
invalidate a target Behavior's evidence even when the target's code is unchanged.
A representation ambiguity blocks the scope even if every executed check passes.

## Remaining boundaries

This branch is a runnable foundation, not completion of every milestone in the
preexisting production roadmap. It does not add production PHP instrumentation,
a real FG schema, durable worker hosting, distributed leases, authenticated
checkpoint storage, a general effect type system or a proof of implementation
refinement. A real consumer must provide its source bindings, adapters, corpus,
codec laws, rollout policy and tests. The synthetic example supplies a concrete
pattern for that integration, not evidence for a private application.

See [validation](behavior-validation.md) for what was actually executed for this
branch, including environmental limits. See the [unified system](unified-behavior-system.md)
for commands and the [method](behavior-effects.md) for the behavioral contract.

## ShenCheck and Vör

No ShenCheck integration was present on the inspected capcov `main`. This branch
integrates the current effects lane explicitly, with source pins for ShenCheck
`42f8e24359fa28c9ce2b733eaa1ddb0cd5e1b06b` and Vör
`80291c4c3f7c28266c9a133b869015ffe8a64b92`. It stages only the checksum-pinned
ShenCheck runner modules, executes qualification and an enrolled observer, then
admits the reports into the same Behavior obligation. Missing tools, unknown
results, failed controls, stale runtime/source bytes and altered evidence block
the existing gate. No alternate acceptance screen or manual verdict merge exists.

The duplicate handwritten protocol model introduced during development was
removed. General ShenCheck campaign features are not reimplemented here; this
bridge selects the existing request-to-effects lane relevant to the Behavior
contract. It preserves the lane's open proof/refinement/liveness claims.
