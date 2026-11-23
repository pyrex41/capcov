# Environment-sensitive call and effect recovery

`capcov discover` can augment its static graph using source-bound environment
facts. A configured handler can lead to an observer, which can lead to a worker;
the existing capability fixed point then exposes the entities and CRUD operations
reachable through that chain. The resulting capabilities use the normal
discover → observe → reconcile → gate workflow.

This is a finite, conservative **may-reach analysis of supplied facts**. It does
not execute the application or claim general PHP/Laravel extraction. A framework
adapter or source-export producer supplies the fact document described below.
The new pass resolves that document's environment-dependent targets. A built-in
Python producer also extracts the limited registry fragment below. It does not
infer those facts from arbitrary source text, prove path feasibility, prove
delivery of queued work, or establish transaction boundaries.

## Explicit research basis: the Nock paper

K. Afonin (~dozreg-toplud), **Nock Compilation (Subject Knowledge Analysis II)**,
*Urbit Systems Technical Journal* 3(2), 2026:
<https://ustj.urbit.org/article/v03-i02/nock-compilation-subject-knowledge-analysis-ii>.
The journal's [citation index](https://urbitsystems.tech/citations) identifies
this article separately from Afonin's earlier *Subject Knowledge Analysis*,
3(1), 2026: <https://ustj.urbit.org/article/v03-i01/subject-knowledge-analysis>.

The implementation borrows the second paper's idea of resolving callable code
using a partially known execution environment. Its purpose here is behavioral
discovery rather than native compilation.

| Paper section | Adaptation in capcov |
| --- | --- |
| §2.2, partial subjects and call graph fixed point | Known deployment values select candidate bindings; absent values retain alternatives. Aliases propagate targets until stable. |
| §2.2, provenance | Recovered edges retain supporting fact IDs and source anchors. This is evidence provenance, not Nock's noun-axis provenance. |
| §2.4.1, worklist | Only changed slot/target support is propagated to dependent slots. |
| §2.3, termination concerns | A finite declared set of slots, nodes and fact IDs bounds this implementation. Cycles need no unbounded context expansion. Resource budgets fail explicitly. |
| §3, preserving branches and failures | Conditions remain in the evidence. Unknown conditions never become false. Error ordering and partial-commit semantics remain behavioral-model obligations. |

We do **not** implement Nock, noun axes, ska-functions, cons denormalization,
homeomorphic embedding, SSA generation or the paper's optimized/general calling
conventions. We do not inherit a proof of correctness from the paper. In
particular, the paper's generalization and recursion machinery is unnecessary
for this deliberately finite abstraction; richer context-sensitive analysis
would need its own termination and soundness arguments.

## Enable in an existing adapter entry

For automatic extraction with the Python/FastAPI/SQLAlchemy adapter and its AST
resolver, use:

```toml
[capcov]
source = "src"

[[adapters]]
name = "python-fastapi-sqlalchemy"
environment_python = {file = "deployment.json", variable = "settings"}
```

Given a source-level `HANDLERS = {"live": publish, "dry": dry_run}` and a call
`HANDLERS[settings["publisher"]](request)`, a configuration file containing
`{"publisher": "live"}` recovers `publish` as a candidate. Literal-key calls
such as `CALLBACKS["saved"](request)` are also recovered, allowing chains through
several registries. The dictionaries must be module-level literals with unique
string keys and local top-level function values. Target source is parsed with
Python's AST and is never imported or executed.

Unknown configuration retains all alternatives and reports a gap. Unsupported
selectors retain known literal candidates with an explicit gap; nonliteral or
shadowed registries yield unresolved calls. Imports, factories, class dispatch,
mutation and arbitrary closure environments are not generally resolved. The
producer adds a separate stability obligation for registry/function rebinding
and correspondence of the named configuration object to the supplied file.
Callback/worker intent is not inferred from a registry name; automatically
extracted edges are ordinary possible calls. Queue semantics need an explicit
framework producer. All parsed Python files and the configuration file join the
source snapshot automatically. This producer currently requires the AST resolver
because its node identities are those of the native Python adapter.

For another producer's source-bound fact export, use:

```toml
[capcov]
source = "src"

[[adapters]]
name = "python-fastapi-sqlalchemy"
environment_facts = "recovery.json"
environment_inputs = ["deployment.json"]
```

Paths are relative to `source`, not the target directory. `environment_facts`
is automatically added to source hashing. `environment_inputs` adds configuration
or other inputs beyond the adapter's ordinary source globs. Every referenced
source/configuration file must be included. Discovery refuses a missing glob,
stale source anchor, noncanonical path or file outside the source root.

Use an `[[adapters]]` entry: `--adapter` overrides configured entries and therefore
does not enable this pass. A source export must use the actual graph node IDs of
the adapter/resolver; no fuzzy name matching occurs. Recovery runs after SCIP
resolution, when enabled, and before capability reachability is calculated.

```sh
capcov discover --target . --out capabilities.json
capcov observe --target . --out observed.json -- pytest
capcov reconcile capabilities.json observed.json --out coverage.json
capcov gate coverage.json
```

The normal probe configuration still applies. Runtime evidence must be newly
recorded over the same expanded source patterns. Configuration changes alter the
source identity, so old runtime evidence cannot be joined to new discovery.
This binds configuration bytes; it does not prove that a running service used
them. That correspondence remains an explicit obligation.

## Fact format

Top-level keys are exactly `schema`, `producer`, `environment`, `nodes`,
`bindings`, `calls`, and `effects`. Schema is `capcov.environment.v1`; producer is
a nonempty versioned identifier. `environment` names a JSON object of scalar
configuration values (string, integer, boolean or null). Missing keys mean
unknown; null is a known value. Boolean false is distinct from integer zero.

Each record has a globally unique `id` and a `source` object:

```json
{"file": "app.py", "line": 12, "sha256": "<SHA-256 of the exact file bytes>"}
```

The line must exist; it locates the producer's assertion, not a verified parse.
All records, including disabled candidates, require valid source anchors.

| Group | Fields beyond `id` and `source` | Meaning |
| --- | --- | --- |
| `nodes` | `node` | Declare a source-backed body using its canonical graph ID. Existing bodies need not be redeclared. |
| `bindings` | `slot`, exactly one of `target` / `from_slot`, optional `when` | A candidate code target or alias to another slot. Multiple bindings are alternatives, never last-write-wins. |
| `calls` | `caller`, exactly one of `target` / `slot`, optional `when`, optional `kind` | A direct or recovered edge; kind is `call`, `callback` or `worker`. |
| `effects` | `node`, `entity`, `operation`, optional `when` | A direct CRUD effect on an entity already in the discovery inventory. |

`when` is a conjunction of exact configuration equalities, for example
`{"publisher": "live"}`. A known mismatch excludes the candidate. An unknown
key retains a possible candidate and emits an unresolved obligation. Alternative
conditions are represented as separate records. Runtime request predicates are
outside this format; callers must conservatively include their possible edges.

Bindings such as `publisher → publish`, `service → publisher`, together with
`route → service`, `publish → observer` and `observer → worker`, recover the full
possible chain. A direct `update issues` on `publish` and `create reports` on
`worker` then appear under the route's existing capability inventory. Labeling
the last edge `worker` does not mean the worker runs synchronously or inevitably.

Unseeded alias cycles and unknown external targets remain unresolved. Seeded
cycles converge. The target relation grows monotonically over finite symbols;
support IDs also grow monotonically. No target code is executed during analysis.
Exceeding a record, target-pair or support budget aborts discovery without
publishing a partial analysis as complete.

## Evidence and trust boundaries

`environment_recovery` in both capabilities and coverage retains input hashes,
producer identity, binding results, edges, conditions, supporting fact IDs,
effect records, the original fact premises and an analysis digest. Configuration
values themselves are not copied from the environment file; avoid secrets in
fact exports because their premises are retained for audit.

The pass adds edges and effects; it never removes existing graph edges, blind
spots or unresolved entries. Thus an imprecise base graph can remain imprecise.
An edge's supporting IDs are a dependency explanation, not a minimal proof tree
or a certificate that all alternative targets were enumerated.

Every export contributes `environment-extraction-boundary` to the normal gate.
It states that source extraction completeness and runtime environment
correspondence remain open. A byte hash cannot discharge either. Existing dated,
reasoned exemptions can acknowledge this boundary, but are not proofs. An absent
or inconsistent binding contributes additional `environment-unresolved` entries.
Even if every resulting entity is exercised, those obligations remain visible.

The source snapshot is read exactly for this pass. Input digests are checked
against it before publication, rejecting observed changes during recovery.
Concurrent editing is not a transactional filesystem snapshot; use an immutable
checkout for qualification runs.

## Integration with the existing tools

Discovery now embeds `environment_claims` alongside `environment_recovery`;
reconciliation retains both. This is a normal validated `capcov.claims.ir.Bundle`,
not a second claim authority. All facts share a static index digest over the
recovery premises, source manifest and primitive graph. Different configurations
have different contexts. Evidence cites source hashes and recovery analysis IDs.

| Existing component | Integration |
| --- | --- |
| Claims IR and Python evaluator | Positive `env_entry`, `env_edge`, `env_touch`, `env_effect` and `env_unknown` premises derive `env_reaches`, `env_capability` and `env_capability_op`. |
| Soufflé | The existing IR compiler emits the same recursive rules; `environment-check --engine both` compares Python/Soufflé closure and checks it against discovery's capability projection. Missing tools, bounds and disagreements fail. |
| Behavior registry | Explicit node owners turn cross-owner calls into `depends_on` edges. Source/configuration/model/query artifacts enroll in the existing dependency graph. Cyclic Behavior dependencies are refused; consolidate mutually recursive bodies into one cutover unit. |
| Qualification and tasks | Import adds static projection, extraction review, effect execution and mapped model-search obligations. Recovery gaps become registry gaps; existing task routing assigns their work. Static agreement cannot discharge execution or review. |
| Shen scenario search | An explicit surface-to-model/query mapping invokes the existing `operations.search` implementation and witness validation. Its model witness does not establish real application behavior. |
| ShenCheck / Vör / runtime probes | Existing execution/proof checks and runtime capture continue to supply their own evidence. Recovery adds candidates and obligations; it does not fabricate engine receipts or automatically enroll a model as a proven implementation. |

`environment-check` reconstructs the canonical rule pack and rejects changed
rules/evidence before evaluating it. This validates graph-relative consequences,
not the truth or completeness of producer assertions. It intentionally creates
no completeness predicates or negative facts. Branch correlations are lost, so
reachable effects can still be infeasible. Delivery, transaction and failure
semantics remain model and execution obligations.

Create a reviewed mapping such as `environment-behaviors.json`:

```json
{
  "format": "capcov-environment-behaviors-v1",
  "source_root": "src",
  "nodes": {
    "app:route": "publish",
    "app:publish": "publish",
    "app:observer": "publish",
    "app:worker": "report-worker"
  },
  "searches": {
    "POST /publish": {
      "spec": "models/publish.ops",
      "input": "models/publish-search.json"
    }
  }
}
```

Every reachable node needs an owner already present in the registry. Use actual
surface and node IDs from discovery; they depend on the adapter. `source_root`,
model/query paths, and the CLI's capabilities/mapping paths are canonical paths
relative to `--root` (the default is the working directory). An empty `searches`
object is allowed and produces model-mapping gaps. Each search query uses the
existing Shen search JSON contract: required `initial`, `calls` and `goal`, with
optional `depth`, `budget` and `fuel`. The mapping does not infer a business model,
initial state, call domain or goal from a call graph.

Starting with the project's existing Behavior registry and check plan:

```sh
capcov discover --target . --out capabilities.json
capcov behavior environment-claims --input capabilities.json \
  --mapping environment-behaviors.json --out environment-claims.json
capcov behavior environment-check --input capabilities.json \
  --mapping environment-behaviors.json --engine both
capcov behavior import-environment --registry behaviors.json \
  --input capabilities.json --mapping environment-behaviors.json \
  --out behaviors-environment.json
capcov behavior environment-plan --registry behaviors-environment.json \
  --checks checks.json --input capabilities.json \
  --mapping environment-behaviors.json --out checks-environment.json
capcov behavior check --registry behaviors-environment.json \
  --checks checks-environment.json --scope publish --evidence evidence
capcov behavior tasks --registry behaviors-environment.json \
  --checks checks-environment.json --scope publish --evidence evidence
```

The generated plan defaults to Python/Soufflé agreement. `--engine python` is an
explicit development-only choice that does not claim Soufflé validation. Its
commands use `python` from the qualification environment. A mapped search check
succeeds only with a verified model witness; bounded exhaustion remains unresolved.
Run one search directly with `behavior environment-search --input capabilities.json
--mapping environment-behaviors.json --surface 'POST /publish'`. The returned
`search.scenario` is the existing scenario format for subsequent replay.

Imports are idempotent for unchanged inputs. They conservatively bind all source
snapshot files to each affected Behavior, plus the capabilities, mapping and
model/query files. The capabilities artifact carries an optional registry
`source_snapshot` binding (`root`, `derived_from`); `behavior inspect` rechecks
both source bytes and source membership. Adding a matching source file therefore
invalidates qualification even when previously recorded files are unchanged.
Existing graph export propagates this staleness through the Soufflé evidence graph.
Changing an enrolled artifact never silently rebaselines it: regenerate from a
reviewed baseline. Model mappings and successful search checks do not automatically
close existing gaps. Review their closure explicitly in the ordinary workflow.

## Validation

`tests/test_environment_recovery.py` contains 27 tests covering configured alternatives, unknown
configuration, alias cycles, callbacks/workers, conditional effects, unsupported
targets/entities, stale source, malformed facts, input containment, budgets,
provenance, discovery/reconciliation/gating, automatic Python registry extraction
and configuration invalidation.
Run it with `PYTHONPATH=src python -m unittest discover -s tests -p
test_environment_recovery.py`. All fixtures are synthetic.

Validation on the implementation branch (base `6b347f5`): 72 focused and adjacent
tests passed (environment recovery, native adapter, reconciliation/gate,
structured-spec adapter and adapter merging); Ruff and `git diff --check` passed.
The wheel install smoke, backpressure checks and fault-harness checks passed.
The broader base-family suite was attempted but interrupted after Tree-sitter
grammar loading stalled; it is not a passing full-suite result. Nix, Go, Soufflé,
Shen and SCIP executables were unavailable in this environment, so the full
pinned-toolchain gates and real-Go-flow check remain to be run in CI/Nix.

Integration validation: 98 focused/adjacent tests pass, including 13 new
integration tests for canonical claims, projection consistency, configuration
contexts, Behavior dependency cycles, idempotence, source-file addition,
qualification receipts, unclassified touches, CLI import/export/plans and Shen
search dispatch. The native three-kernel test compares Python, interpreted
Soufflé and compiled Soufflé for live/dry/unknown configurations; it is assigned
to the existing Soufflé CI family and was skipped locally because Soufflé was
unavailable. The Shen dispatch test mocks the native call and is not a native
Shen validation result. Wheel build/install smoke and Ruff pass.
