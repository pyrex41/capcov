# Learning semantics with scoped evidence

Research question: does evidence change which programs, abstractions and semantic distinctions are learned, beyond filtering a fixed candidate set? These standalone pilots use Capcov's native Shen evaluation API. They do not modify qualification policy or assert application correctness.

## Reproduce from repository root

In `nix develop .#shen`, run:

```sh
PYTHONPATH=src python3 experiments/semantic-learning/calibrate.py > /tmp/calibration.json
PYTHONPATH=src python3 experiments/semantic-learning/identify.py > /tmp/identification.json
PYTHONPATH=src python3 experiments/semantic-learning/library.py > /tmp/library-result.json
```

Each script checks its expected control outcome. The adjacent JSON files record the initial run. `calibration.json` includes native receipts, inputs and model/runtime identities. An unexpected result is a reason to inspect the receipts, not to update snapshots automatically.

## Results and interpretation

* Calibration: on a pending job, one and two successful committed sends end in identical row states in each model. Only the legacy model emits twice. Observation hides intermediate responses and projects `emit` effects; raw Shen effects include database writes. The intended model assumes atomic publication and marking, not exactly-once external delivery.
* Identification: under an emissions-only contract, `a` and `ab` leave both candidate models alive; `aa` distinguishes them. One active target query selects the correct model in both worlds and predicts all three withheld interleavings. One uniformly selected passive query identifies the model with probability 1/3. Active planning also evaluates candidate models; target-query efficiency isn't total compute efficiency. Target and candidate here are literally the same fixture: this checks identifiability, not induction from an independent implementation.
* Library: collapsing adjacent duplicate sends unconditionally gives 3 mismatches in 6 held-out model/workflow pairs. A guard derived from the shared repeat-emission probe yields 0 in 6. Both fixed filtering and witness specialization select it, each retaining 21 of 26 original command occurrences. Thus evidence changes the compression-only selection, **not** the outcome relative to filtering. This is a hand-authored rewrite grammar, not Stitch, learned guard synthesis or a downstream task-solving benchmark. Costs approximate grammar size, not measured storage. Contracts and results are bounded; the library pilot observes emissions only.

## Decision log and program backlog

1. **Foundation (partial):** add a frozen campaign manifest with executor and learner identities, task-family splits, proposal and verification budgets, complete per-arm query ledger, artifact hashes, seed and status (supported within bounds / counterexample / inconclusive). Keep descriptive models separate from normative claims. Invalidate evidence after a dependency change; demonstrate that unrelated receipts survive.
2. **Library learning (next):** keep the current filter as the incumbent. Add a reservation or ledger domain with different failure behavior, an independently implemented adapter, and tasks collected independently of the rewrite grammar. Specify observer contracts before inspecting results. Add exact macro extraction as a semantics-preserving control distinct from semantic rewriting. Enumerate guard expressions rather than supplying the right guard; compare fixed filtering versus witness-directed proposal ordering with equal budgets and grammar. Measure program plus library size and downstream synthesis on withheld workflow families. Do not promote the pilot rule as a primitive.
3. **Program synthesis (parallel after measurement):** fix the library, executor and task contracts. Compare examples only, equal-budget generated tests, and minimized counterexamples for the same synthesizer. Score held-out task success and total cost per solution. Introduce an LLM only after deterministic controls and logging work.
4. **Model induction (parallel):** replace fixture selection with Reversa-derived, source-linked candidate clauses and explicit unknowns. Use independent adapter observations, not target source, for scoring. Compare passive traces and active disagreements; penalize models that admit everything, allow abstention. Separate ambiguous outcomes from execution failures. Keep external intent decisions out of the learner.
5. **Coupling:** admit one revision at a time; cross-evaluate old/new models against old/new programs and independent behavior. Compare joint learning with each component frozen and the strongest filter. Track reuse, regressions and requalification cost after source changes. Stop at separate learners if coupling does not improve held-out outcomes.
6. **Language promotion and transfer:** only for a concept that helped on an independent task family, compare expanded code, library abstraction and typed effect/primitive. Use Gleipnir for backend conformance, Capcov for application-level evidence. Require transfer or demonstrably cheaper reusable obligations before changing the language. Publish negative results, budgets, counterexamples, receipts and unresolved assumptions alongside successes.

## Guard discovery follow-up

Run `PYTHONPATH=src python3 experiments/semantic-learning/guard_search.py > /tmp/guard-search.json` in the same shell. `guard-search.json` records the run. All arms share five fixed emissions-count probes, 40 atomic predicates and 780 conjunctions, complexity-first ordering with 32 seeded tie breaks, and a cap of four full candidate assessments (two models × two training workflows per assessment). A no-selection result keeps the original program. Counts are logical candidate assessments, **not** physical native invocations or elapsed time: model observations are memoized. Seeds vary search order, not tasks. This grammar contains redundant expressions on purpose; signature filtering is the important control.

| Policy | Found useful training guard (of 32) | Total candidate assessments | Predicates scanned |
|---|---:|---:|---:|
| Fixed filtering | 15 | 108 | 182 |
| Filter unique training-world enablement signatures | 32 | 81 | 308 |
| Skip guards that reproduce a known failing rewrite | 32 | 62 | 308 |

Feedback saved assessments but did not improve selection over signature filtering. No selected guard introduced an emissions mismatch on the withheld histories for the two uniform SQLite policies. Every selected guard failed on the mixed policy: counting emissions on the five fixed probes cannot distinguish a world that deduplicates both keys from one that deduplicates only `a`. Thus searching this grammar longer cannot solve the observed transfer failure. The SQLite adapter is an independently coded experimental executor, not production validation.

Post-hoc diagnostic: rebind the probe's focal key at each retry site, without changing the selected predicate. All selected rules then matched on the three mixed-policy test histories, with shortened histories in two of three. This binding was supplied by the investigator, not discovered, and those histories are no longer fresh evaluation data. Next decision: can a learner propose the key binding from a discrepancy and predict untouched heterogeneous policies (e.g. payload- or transaction-scoped deduplication)? Freeze those tests before adding the proposal operator.
