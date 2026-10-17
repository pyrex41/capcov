# Evidence-backed Shen reasoning workbench

`capcov reason` connects source inventory, symbolic obligations, checked
derivations, finite relational generators, stateful observations and replay.
It extends `capcov system`; existing models and claim-admission rules remain
compatible. Application code and state adapters stay in the consuming repository.

## Run

Use the pinned `nix develop .#shen` environment. Source extraction for Go/PHP
uses the optional `treesitter` extra; its grammar wheels are pinned in `uv.lock`
and do not download grammars during extraction. Python extraction is stdlib-only.
For the existing Nix `withTreesitter` package, extraction can also use the
provided language pack when direct grammar bindings are absent; its grammar
availability remains a property of that package/environment.

```sh
uv sync --frozen --extra treesitter
PYTHONPATH=src python -m capcov reason compile \
  --spec tests/claim_semantics/fixtures/systems/workspace.ops
```

The workspace example discharges eight model obligations: postconditions and
the legal-status invariant for create, rename, close and delete-account.
The ledger's postcondition, including total-balance conservation, is discharged;
its nonnegative-balance invariant remains an open obligation in this version.
Compilation does not execute examples to establish these results.

Every command accepts `--out FILE` and native commands accept `--timeout SEC`.
Exit 0 means the requested check completed without its named failures; exit 1
means open obligations, missing requested witnesses, mismatches, stale evidence
or unstable replay as applicable. Exit 2 means invalid input or operational
failure. No exit code establishes application-wide correctness.

| Command | Input |
| --- | --- |
| `compile --spec M` | Derive model obligations; no input file |
| `prove --input Q` | `{left: [Formula], right: [Formula]}` |
| `check --input P` | A sequent proof artifact |
| `relation --input R` | A typed relational plan |
| `solve --input Q` | `{program: R, inputs: {...}, budget?: N}` |
| `extract --root DIR --input Q` | `{files: [relative paths], revision?: label}` |
| `bind --input Q` | `{inventory: I, claims: [...], gaps?: [...]}` |
| `invalidate --root DIR --input I` | A bound source inventory |
| `search --spec M --input Q` | `{initial, calls, goal, depth?, budget?, fuel?}` |
| `scenario --spec M --input S --adapter COMMAND...` | A stateful scenario |
| `minimize --spec M --input S --adapter COMMAND...` | A reproducible failing scenario |
| `verify --root DIR --spec M --input Q --adapter COMMAND...` | `{inventory, campaigns, minimize_runs?: N}` |
| `properties --spec M --input Q` | `{states: [...], goals?: [{id, predicate}]}` |

The Python APIs expose the same operations. The adapter argument vector runs
consumer-selected executable code; none of the data languages permits eval,
imports, shell commands, or host callbacks.

## Sequent kernel and compiler trust boundary

A sequent `L |- R` means the conjunction of L implies the disjunction of R.
Formulas are JSON lists:

```json
{"left": [["and", ["atom", "authorized"], ["atom", "exists"]]],
 "right": [["atom", "authorized"]]}
```

Constructors are `atom`, `true`, `false`, `not`, `and`, and `or`. The native
search uses invertible classical sequent rules. Every successful search returns
an explicit derivation and checks it with `proof-check.shen`. `reason check`
loads that kernel without proof search or the system evaluator. Identity,
truth/falsity, negation, conjunction and disjunction rules verify their exact
premises. Invalid propositions return propositional countermodels. A countermodel
to the Boolean abstraction is not necessarily a reachable application state.

Artifacts bind the contexts, derivation, kernel/library bytes and runtime binary
identities. The `check` Python API accepts expected `left` and `right` contexts:
callers admitting evidence must use those to prevent theorem substitution.
Rehashing an invalid proof cannot make the kernel accept it.

`compile_system` is a separately identified **trusted symbolic compiler**. It
uses the existing Shen construction judgments, then derives sufficient
preconditions for prospective action paths, before runtime postcondition checks.
It does not use a runtime postcheck as a premise proving itself. The compiler
implements exact-key substitution, disjoint-key facts from stable preconditions,
frame rules, conditionals, successful `require` paths, row-local universal
invariant instantiation, preservation under deletion, and exact additive
normalization. Its hash and its universal instances appear in the report.

The propositional checker does not independently verify the compiler's
weakest-precondition transformation, arithmetic normalization, or first-order
instantiation. Those transformations, the Shen runtime, and declared model
semantics remain in the trusted base. This is not a proof of the PHP/Go source,
the extraction mapping, arithmetic totality, schema preservation, or termination.
Operational exceptions and fuel exhaustion are distinct from successful paths.
An application accepting a different state abstraction requires explicit review.

Unsupported aliasing, affected quantifiers, loop induction, nonlinear arithmetic,
and proof-budget excess remain named open obligations. Deletion-only loops can
preserve row-local universal invariants; general loops need an induction rule.
Current proof limits: 128 formula nodes, 12 atoms, nesting 32, derivation depth
128, 256 sequents per batch, bounded output and subprocess time.

## Mercury-inspired relational plans

A single typed plan can run under different input/output modes. This example
generates two increments and consumes one logical capability on each branch:

```json
{
  "variables": {"x":"int32", "y":"int32", "z":"int32"},
  "inputs": ["x"], "outputs": ["y","z"],
  "capabilities": ["transaction"], "determinism": "multi",
  "body": ["all", [
    ["domain", "y", ["1","2"]],
    ["add", "x", "y", "z"],
    ["consume", "transaction"]
  ]]
}
```

`solve(program, {"x":"3"})` returns `(y=1,z=4)` and `(y=2,z=5)`.
Making all variables inputs and declaring `semidet` checks supplied values.
Finite `domain` goals support synthesis; they are explicit bounds, not implicit
enumerations of all integers. Values are canonical int32 or bounded text.

Goals: `literal`, `domain`, `equal`, `less`, `add`, `consume`, `all`, `any`.
Shen analyzes grounding and lower/upper solution cardinality compositionally.
It rejects use-before-ground, missing outputs and overly strong declarations.
`det` means exactly one successful solution, `semidet` at most one, `multi` at
least one, and `nondet` any number; these classifications do not promise freedom
from arithmetic errors or resource failure. Bounds encoded as 2 mean two or more.
Conservative analysis may reject a semantically deterministic program.

Capabilities are **affine logical resources**: unused resources are allowed,
consuming twice is rejected, and alternative branches must leave the same set.
Backtracking carries independent contexts. They do not authorize real host I/O
and do not establish exactly-once delivery. This deliberately finite language
does not claim Mercury-compatible compilation of arbitrary Shen programs.

## Goal-directed scenario search

Shen Prolog chooses commands, outcome branches and successor histories directly.
Iterative deepening finds a shortest command history within the supplied domains.
The result is reexecuted through the existing native model and patch checker.
Search does not merge histories just because their states are equal: repeated
effect intents remain visible.

```json
{
  "initial": [{"table":"job", "key":"j",
               "fields":{"status":"pending", "payload":"hello"}}],
  "calls": [{"command":"send", "args":{"id":"j"}, "outcome":"committed"}],
  "goal": {"emitted":"delivery-attempt", "count":2},
  "depth": 2
}
```

Run against `tests/claim_semantics/fixtures/systems/outbox.ops`. This produces
two sends with the same successor state and two observable intents. Other goals
are `{state: "[...predicate...]"}` and `{violation: true}`. The latter searches
for the model's prospective invariant/postcondition rejection.

`calls` can alternatively be a typed generator:

```json
{"relation": {"variables":{"id":"text"}, "inputs":[], "outputs":["id"],
              "capabilities":[], "determinism":"det",
              "body":["domain","id",["j"]]},
 "inputs":{}, "command":"send", "outcome":"committed",
 "arguments":{"id":"id"}}
```

The relational compiler checks the generator before its solutions become the
call domain. Generator identity and solutions travel with the search report.
No witness means exhausted within the stated domain/depth, never universal
unreachability. A transition-budget exhaustion is an operational failure.

## Source evidence and Souffle change impact

`extract` inventories actual syntax in explicit Python, Go and PHP files:
functions, guards, assignments, calls, returns and exceptions where supported.
Anchors record file hashes, symbol, source lines, exact text and text hashes.
These are syntactic observations. They do not infer intended business behavior.
An LLM or developer can propose claims using these anchors, but the proposal is
not silently promoted to a proved specification.

Each supplied claim has exactly `id`, `statement`, `kind` (`legacy` or `target`),
`anchors` (anchor IDs), `depends_on` (claim IDs), and `obligations` (model IDs,
for example `send:postcondition`). Gaps have `id`, `question`, and `claims`.
Cycles, missing references and fabricated anchors fail validation. Freshness
checks reconstruct anchors from unchanged source; matching hashes alone are
insufficient to manufacture a source observation. Changed files invalidate all
their anchors and the transitive dependent claims. Gaps persist.

The default closure is stdlib Python. `invalidate(root, inventory,
engine="souffle")` runs the packaged monotone `evidence.dl` and requires agreement
with the independent Python closure. Facts contain digest identifiers, avoiding
fact-file quoting ambiguity. This closure concerns inventoried dependencies only;
absence of an extracted dependency never proves whole-program completeness.
`revision` is a caller-supplied label; actual source bytes are bound separately.

## Stateful adapters, replay and shrinking

The scenario protocol sends **one whole history to one process**:

```json
{"protocol":"capcov-scenario-adapter-v1", "initial":[],
 "steps":[{"call":{"command":"op","args":{},"outcome":"unknown"},"choice":"1"}]}
```

The adapter returns exactly `protocol`, `observations`, `choices`, and `controls`.
Each observation has `state` and ordered `effects`. The choices must exactly
acknowledge the supplied tape. Unknown outcome choice `0` selects abort and `1`
selects commit. Other supported outcomes use choice `0`. Expected model results
are never sent to the adapter. It must independently execute, reset and abstract
the application. Snapshot/state/effect fidelity is its responsibility.

The harness compares each observation using its actual predecessor state and
stops conformance checking at the first discrepancy; `checked_steps` records the
checked prefix. It preserves the entire observed history and separately reruns
the entire scenario. Replay equality includes observations and declared controls.
A clock, random source, scheduler or external service outside the adapter's
control can still make execution nondeterministic. This is an integration boundary
for controlled executors; it is not an Antithesis hypervisor or sandbox.

The synthetic `scenario-adapter.py` fixture is independently written and imports
no model evaluator. `--mutant` doubles a send effect. Integration tests search a
retry history, execute the mutant, reproduce the discrepancy and reduce it to a
single send. Deletion minimization preserves the first failing command and exact
execution identity. Operational failures do not reproduce the target failure.
The result explicitly records budget exhaustion and whether single-step deletion
minimality was reached. Consumer-defined stronger failure equivalence can be
added before treating minimized histories as the same business defect.

## Integrated verification and evidence admission

The optional Antithesis bridge evaluates schema/invariant safety properties and
named state-reachability objectives directly in Shen:

```python
from capcov.operations.properties import observe, publish
report = observe(source, observed_states,
                 [{"id": "recovered", "predicate": recovery_predicate}])
publish(report)  # explicit SDK emission; requires the installed Antithesis SDK
```

`publish` uses Antithesis's documented third-party-framework `assert_raw` API.
It emits a catalog entry (`hit=False`) before runtime observations, with stable
model-bound IDs and messages. Safety maps to `always`, reachability to `sometimes`.
Malformed schema produces a safety failure; dependent properties are unevaluated,
never counted as passing. A supplied `sink` supports testing or other backends.
No SDK is imported and nothing is emitted until `publish` is explicitly called.
The application/executor still supplies faithful observed states. This adapter
does not provision an Antithesis environment or establish liveness from a single
reachable state. See the [official API](https://antithesis.com/docs/generated/sdk/python/antithesis/assertions.html).

`verify` reconstructs source anchors, derives and independently checks model
proofs, searches campaigns, executes reachable scenarios, verifies replay, and
minimizes reproducible conformance mismatches. Its claim report keeps separate:

- source anchoring and freshness;
- proved and open model obligations;
- witnessed campaigns;
- concrete refuting executions and unstable replay;
- unresolved questions.

A campaign has `id`, `claims`, `initial`, `calls`, `goal`, and optional `depth` and
`budget`. The consumer supplies links between campaigns, model obligations and
source claims. This report does not create reviewer approval, source/model
equivalence, closed-world completeness, or operation-wide conformance facts.
The existing `system claims` admission boundary continues to accept case-scoped
evidence only.

## Verification and remaining work

```sh
CAPCOV_SHEN_REQUIRED=1 PYTHONPATH=src uv run --frozen --extra treesitter \
  python -m unittest tests.claim_semantics.test_reasoning -v
```

Native tests are assigned to the Shen family; change-impact tests to Souffle.
The full pinned CI accepts no missing-runtime skips for those families. Tests
include independent truth tables, rehashed proof/anchor forgeries, semantic
mutants, unsound mode declarations, capability duplication, lost-response
choices, replay instability and the complete source-to-counterexample loop.

Remaining substantive work is general inductive/linear-arithmetic derivations,
source-to-model equivalence checking, additional source languages, protocol
refinement across concurrent histories, adapter implementations for real services,
and an executor that controls scheduling, time, entropy, network and persistence.
These are explicit capabilities beyond this implemented workbench, not guarantees
obtained by choosing Shen or by replaying a model twice.
