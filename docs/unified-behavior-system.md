# A unified recovery, execution and qualification system

`capcov behavior` connects recovered knowledge, an executable target and scoped
validation in one consumer-owned registry. Reversa-style recovery supplies
traceable hypotheses and gaps; capcov supplies existing discovery, models,
evidence and checks; the new Behavior layer connects store contracts, Shen Step
execution, migration decisions and cutover obligations.

The system is useful before an entire application has been recovered. Run one
important Behavior through the whole loop and retain unresolved knowledge as
explicit gaps. The [synthetic publication example](../examples/behavior-publication/README.md)
is the executable reference.

## Shared artifacts

| Artifact | Producer | What it establishes |
| --- | --- | --- |
| Source inventory / recordings | Existing capcov tools and application observers | Scoped source or execution evidence |
| Recovery exchange | Recovery agent plus reviewer | Source-linked static claims and explicit gaps |
| Behavior registry | Consumer | Baseline, dependencies, access matrix, obligations and decisions |
| Legacy `.ops` / other model | Consumer using existing Shen tooling | Allowed modeled outcomes under stated assumptions |
| Target Step program | Consumer; admitted and interpreted in Shen | Closed phase/effect/continuation structure |
| Protocol model and generated config | Vör authoritative model; ShenCheck TLA+ generator | Finite safety with independent reference checks and required defect controls |
| Reviewed check plan | Consumer | Which command must establish each authored obligation |
| Execution receipt | `behavior check` | Actual command completion bound to source, scope, inputs and logs |
| Qualification report | `behavior gate` | Whether all enrolled obligations currently have admissible evidence |

No row substitutes for another. A label such as `validated` on a registry claim
is metadata, not permission to skip a check. A green exit from a consumer's command
has exactly the meaning of that reviewed command. Pin the executable/toolchain,
check helpers, environment manifest and all semantic inputs in production plans.
The command runner does not automatically capture arbitrary inherited environment
variables or prove that a custom test has meaningful assertions.

## Workflow

From the repository root, with the example's dependencies available:

```sh
capcov behavior validate --registry examples/behavior-publication/registry.json
capcov behavior inspect --registry examples/behavior-publication/registry.json --scope publication
capcov behavior admit --input examples/behavior-publication/route.json
capcov behavior check --registry examples/behavior-publication/registry.json \
  --checks examples/behavior-publication/checks.json --scope publication \
  --toolchain /absolute/path/to/toolchain.json --evidence /tmp/publication-evidence
capcov behavior gate --registry examples/behavior-publication/registry.json \
  --checks examples/behavior-publication/checks.json --scope publication \
  --toolchain /absolute/path/to/toolchain.json --evidence /tmp/publication-evidence --cutover
```

The evidence directory must be empty for a new execution. Store reports outside
that directory: it contains only receipt JSON and their logs. `gate` revalidates
stored receipts and current source hashes without rerunning the checks. Exit 0
means the requested result passed, 1 means incomplete or incompatible, and 2
means malformed input or an operational error. A gate result is not deployment.

`--root` selects the root against which enrolled paths and commands resolve.
`--scope` can be repeated; omitting it selects all Behaviors. Scope includes
transitive behavior dependencies, attached claims/gaps/decisions and all enrolled
writers of selected stores. Cyclic dependencies must be consolidated into a
cutover unit, rather than treated as recursively proven premises.

Additional commands:

```sh
capcov behavior import-recovery --registry REGISTRY --input RECOVERY --out UPDATED
capcov behavior tasks --registry REGISTRY --checks CHECKS --evidence EVIDENCE
capcov behavior graph --registry REGISTRY --out /tmp/behavior-graph
souffle -F /tmp/behavior-graph -D /tmp/behavior-graph /tmp/behavior-graph/evidence.dl
capcov behavior compare --registry REGISTRY --checks CHECKS --evidence EVIDENCE \
  --scope BEHAVIOR --input COMPARISON
```

Recovery import writes a new registry; it does not alter the input. The graph
exports the whole enrolled dependency graph with hashed IDs and `ids.json` for
lookup. Its `stale.csv` is a whole-graph result; the CLI inspection is scoped.
Existing source extraction remains under `capcov reason` and the mapping tools.
A comparison input has `scenario`, `legacy` and `target`. Its qualification is
recomputed before any approved difference is accepted.

## Division of responsibility

Shen owns target operational semantics and the object-language admission judgment.
Existing Shen models and contract proof tools remain usable as additional checks.
Souffle evaluates relational graph facts for impact; it does not infer PHP effects
without an extractor supplying facts. TLA+ checks selected concurrent protocols;
it does not replace handler types or stateful adapter tests. Python remains the
existing CLI, process, serialization and adapter host.

The target is deterministic over explicit inputs and effect replies, while the
legacy model can admit multiple histories. The migration policy relates them.
A target can choose a stable ordering from several legal legacy orders, but that
choice belongs in a reviewed contract. If it strengthens atomicity or changes an
error response, qualify the replacement guarantee instead of hiding the diff.

## Delivery order and present scope

Start with a broad, shallow map; implement one vertical unit; expand independent
units after its gates work. Recovery roles can share obligations, but this CLI
does not launch agents or count agreement as observations. Tasks are suggested
work items ordered by user importance.

Implemented now: strict registry validation, four store layers, access matrix,
source drift detection, static recovery import, priority tasks, graph export,
closed Shen Step execution, request/result correlation, host checkpoints,
effect transcript replay, fresh check execution, integrated ShenCheck/Vör qualification and concrete-prefix checking, exact decision comparison,
scoped cutover-policy reporting, and a stateful publication/TLA+ example.

Still consumer responsibilities: source-model correspondence, complete production
entry/corpus coverage, real authorization/tenancy adapters, numeric and sentinel
codecs, durable worker/checkpoint hosting, provider contracts, performance budgets,
rollout and rollback. No live application has been cut over by this branch.

The [method](behavior-effects.md), [Reversa comparison](comparison-reversa.md),
[capcov baseline comparison](comparison-capcov-baseline.md) and
[validation record](behavior-validation.md) describe these boundaries in detail.

## One protocol lane, one result

For a check with `engine: "shencheck-effects-v1"`, `behavior check` automatically
executes ShenCheck's reviewed cohort. It is not an alternate evaluator. The
source pins ship in `capcov.behaviors/shencheck-effects-pins.json`; operator
locations are supplied by `--toolchain` using
[`toolchain.example.json`](../examples/behavior-publication/toolchain.example.json).
No private ShenCheck code is vendored. Install the pinned checkouts and bootstrap
Vör once; an enrolled obligation cannot silently skip if those tools are absent.

The engine checks the healthy model and four mutants, retaining the exact
counterexamples, property identities, source/runtime identities, generated TLA+
and logs. If `observe` is enrolled, its command receives the generated healthy
model path and a new output path. It must write a fully observed
`effects-history-v1`. ShenCheck checks that history automatically under the same
model; missing or incompatible observations block the obligation. The publication
observer covers the actual commit/response prefix only, not the worker protocol.

`behavior gate` repeats source, runtime and artifact validation without executing
the campaign. It reports counterexample paths and remaining generic claims in
`engine_evidence`, alongside all other obligations. Tests, UNKNOWN, model safety,
finite trace conformance and general proof remain distinct. General campaign
search/shrinking features in ShenCheck are not exposed as a second acceptance path.

This bridge is pinned intentionally: upgrading ShenCheck or Vör requires reviewing
the interface, updating hashes and rerunning the controls. An upstream change must
not silently alter what a previously green Behavior report means.
