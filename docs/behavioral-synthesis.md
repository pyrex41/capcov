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
