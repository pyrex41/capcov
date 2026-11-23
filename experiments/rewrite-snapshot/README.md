# Snapshot publication: a real Python → JS rewrite trial

`source.py` is a small experiment adapter over Capcov's production `src/capcov/cas.py`. It writes actual files in fresh temporary stores. Astra received the complete adapter, library source and observation contract, not access to either evaluation suite. `initial.cjs` and both pairs of repair programs are complete sampled Node executables. Inputs and model identifier are retained in `*-input.json`. The rewrite may use memory because persistence across workflows, process crashes, materialization and concurrency are outside this contract. Byte-identical published manifests and their digests, named reads, and error categories are observable. Legacy behavior is the authority, not necessarily ideal behavior.

The first frozen campaign (`result.json`) found no mismatch on 4 ordinary tests, 15 challenge histories, or 24 withheld parent/child workflows. An exploratory path sweep after inspecting the first JS implementation found a new distinguishing case. The subsequent **targeted** follow-up (`path-result.json`) froze a separate 12-workflow corpus covering other path spellings and accepted controls before asking for repairs. Both repairs received the same initial JS and ordinary test evidence, in fresh tool-free Astra sessions, one call each. Only the feedback arm received three reduced old/new discrepancies. This controls generation call count, not input tokens, elapsed time, oracle executions or exact inference cost. No mutant was planted. No Jev ranking: the compatibility brief already determines the required behavior.

The initial and ordinary-test repair each matched 6/12 targeted workflows. The witness-informed repair matched 12/12, and all three retained 24/24 on the original withheld workflows. These are correlated variants around one observed discrepancy, not independent projects. This harness uses a small experimental differential runner over real executables, not a new production `capcov rewrite` command. Shrinking deletes operations while preserving the final discrepancy's output categories, not proving global minimality. The receipt records both actual outcomes for every miss.

Offline replay (Python with Capcov source available, Node supporting `--permission`):

```
python3 experiments/rewrite-snapshot/experiment.py score
python3 experiments/rewrite-snapshot/path_followup.py replay
```

Replay regenerates the score JSON files. `generate` and `path_followup.py sample` are separate **paid resampling operations** and overwrite arm files; use a copied directory/worktree for new trials. Next generalization test: freeze tasks from other real subsystems before inspecting their rewrites, pin the reference runtime, and repeat paired repairs over seeds. Do not infer cross-platform filesystem or concurrency compatibility from this result.
