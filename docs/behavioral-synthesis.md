# Behavioral synthesis

The experimental learner operates on finite, pure Boolean observations. A task supplies named Boolean inputs and an observed Boolean result. Its obligations apply only to the specified observation.

## Invent a library from sibling workflows

    python -m capcov synthesize research.json --induce-training --library-out library.json --out report.json --max-cost 12 --max-terms 500000

Use a top-level `tasks` array of siblings containing `id` and `examples`. Each example is `{"input":{"a":true,"b":false},"output":true}`. With `--induce-training`, omit all training program ASTs. The wake search solves the sibling tasks from observations. Repeated variable-renamed syntax trees become parameterized definitions if they reduce the measured size of the rewritten corpus including the definition. Distinct suffixes shared by formal argument bindings supply a simple search prior when they uniquely match fields in a new target.

A program-free `target` with `train_examples` and `heldout_examples` runs an explicit sparse-prediction experiment. Baseline and library searches receive identical fitting evidence and budgets. Search selects the first fitting expression by grammar cost and deduplicates on observable outputs. A uniquely role-bound learned call is one grammar production. Both selected programs are checked by the reference interpreter before scoring. Saved reports include their ASTs, search attempts, stopping conditions and results. Supply `--emit-go policy.go` to emit the selected program.

## Fit a known contract and challenge it

    python -m capcov synthesize acceptance.json --library-in library.json --out result.json --max-cost 12 --max-terms 500000 --max-probes 32

For porting, give the target its full `examples` array and optional `reachable_inputs`. A probe is `{"id":"fixture-case","input":{"a":true,"b":false}}`. The producer owns reachability and independent adjudication. Keep the target operation and its aliases out of library invention. Search fits both baseline and assisted programs to every known answer. For each new projected input, it looks for another assisted program satisfying the entire contract and producing the opposite output. This produces a disagreement witness or a bounded search receipt. Previously covered feature vectors cannot distinguish programs in this DSL. Resolve raw witnesses against an independent oracle, retain exceptions and append the answers to the contract. A finite check only describes the exercised inputs and projection.

## Run an inventory

    python -m capcov synthesize-batch operations.json --out batch.json --max-families 100 --max-cost 9 --max-terms 50000

The input maps IDs under `operations` to `family` and Boolean `examples`. Per family, the final eligible ID in sorted order is isolated from invention. Search first solves the eligible siblings, then invents a library and fits the target's entire known contract. Inspect the budget stops, exclusions, actual call use and both fit results. `capcov learn evaluate` separately compares named observations in training and held-out operations, keeping candidate evidence independent from incumbent consistency.

## Operation-scoped agent workflow

The implementation plan has three stages. Solve observation-only siblings and invent a reusable Boolean library. Fit the full target contract and search for reachable disagreements. Route the resulting obligation to replay or intent review and retain a revision-bound receipt.

Start with `capcov reason next --operation ID --project capcov.search.json --json`. Dispatch the returned action by its kind. A search action carries argv for `reason run`. A witness carries the concrete projected input, both predictions and a seed intent packet. Collect independent observations, attach the business sources and the packet under the operation's `intent`, then request review. Store the reviewer's cited response under `recommendation`. Record an independently accepted rule under `accepted` when available. A previously confirmed decision may be supplied directly.

The project's `target.examples` holds mandatory Boolean expectations for this projection. Keep descriptive PHP and Go observations in the intent packet while deciding which expectations apply. The search validates all examples plus accepted projected cases. For a richer observable, define a specific Boolean projection first. The caller supplies reachable probe inputs and is responsible for their reachability.

A replay action can carry argv supplied by the project. The orchestrator runs the adapter in its fixture environment. To check the result, attach `candidate_replay` with the operation's `revision`, an evidence `source` and `observations` of the form `{"input":{"field":true},"output":false}`. Rerun `reason next`. A changed revision invalidates the receipt. A passing projection covers the listed cases only. The operation can also specify a pinned intent packet without a synthesis target.

Search receipts live under `.capcov/search` next to the project by default. Pass `--state-dir` to share them between workers. Search resumes from completed receipts; an interrupted enumeration restarts from its declared bounds. Use `--emit-go PATH` to materialize a fitted candidate. See [the runnable projects](../examples/search-projects/README.md).

The sleep phase samples programs from the Boolean grammar including invented functions, executes bounded synthetic truth tables, and learns a non-neural production ranking from those tasks and solved siblings. Search compares features of the target's known examples to these training tasks. The ranking orders productions of the same cost; candidate acceptance still uses the interpreter on every example. The baseline uses the original grammar and ordering. Set `bounds.sleep_samples` (default 96, maximum 512) to control the number of generated tasks. The receipt includes the policy, library digest, wake results, and both searches.

For an existing whole-inventory Boolean projection in the `synthesize-batch` input format, set the project to `{"schema":"capcov/search-project/v1","revision":"<source revision>","corpus":"projection.json","max_siblings":32}`. Supply the census ID to `--operation`. Capcov selects siblings from the same family in stable ID order and reports how many fit the limit. Every selected target example is retained. With a corpus derived from incumbent observations, the fitted contract characterizes the incumbent. Product qualification requires a projection of the desired behavior.
