# Behavioral induction eval

Incubate here while the oracle is closely tied to Capcov. The unit being evaluated is **an executable hypothesis**, not its English rationale. Keep a small independent runner; extract it when a second oracle consumes the same artifact contract.

## Current task and evidence boundary

A fresh tool-free Luna process sees reset histories and one signal bit per call. It can compose generic sequence operators but cannot inspect the device. Jev chooses among hypotheses mechanically consistent with the disclosed examples. Capcov executes the Shen target to obtain labels. No Jev probability or model explanation is test evidence. The signal bit is the only observable under test. The oracle precomputes all 36 state/input transitions; external I/O and concrete application behavior are out of scope.

## Retrospective repair trial

The parent transcript is `luna-jev-result.json`. Freeze the failed proposal and its six already-disclosed histories, then compare observations only to the same observations plus failed expression and predicted-versus-actual bits. Neither arm sees the diagnostic library, target code, or held-out scores. `repair.py` also searches for an additional distinguishing probe if one is needed by the diagnostic panel. This is a retrospective task-level comparison, not a fresh benchmark or a multi-seed efficacy study.

Audit of diagnostic power: four possible lookup scopes × two record selectors × three compared field sets plus two constants = 26 rival implementations. The six histories eliminate 24. Both surviving implementations select the last record with matching first field; comparing both fields after that lookup is equivalent to comparing only the second field. No additional example is required *in that family*. Finite observations do not uniquely identify an unrestricted law. The evaluator designed the family with knowledge of the target; this is a diagnostic, not an unbiased prior over all programs.

Recorded run: the examples-only response failed JSON parsing. Repair produced four proposals, two consistent; both passed all 340 histories of lengths 1–4 and 96 seeded histories of lengths 5–10. The 340 include training examples. Jev chose h2; h0 scored equally well. An earlier attempted control call also failed parsing before failure capture was added. Do not count invalid output as a semantically wrong hypothesis or claim a measured causal repair benefit.

## Reproduction

From repository root in the Shen shell:

```
CAPCOV_SHEN_IMPL=shen-go PYTHONPATH=src python3 experiments/semantic-learning/llm/replay_repair.py
```

Replay rechecks the parent hash, native identity, and stored scores without contacting either provider. For **new paid sampling**, run `repair.py` in place of `replay_repair.py` with authenticated Pi and `JEV_API_KEY`. Copy the existing report first: currently the sampler writes `repair-result.json`. Prompts, rejected proposals, failure detail, selections and scores are retained in the report. Provider calls are not deterministic.

## Next eval milestones (before splitting a repo)

1. Use immutable per-run directories with a manifest pinning evaluator, task, DSL, seeds, budgets, and provider versions where available. Capture raw responses before parsing, classify transport/format/semantic failures separately, and report both valid-output rate and predictive accuracy conditional on validity. Use equivalent structured decoding or format-retry policies across arms.
2. Pre-register several targets generated independently of prompt tuning, vary alphabet and history length, and include intentionally underdetermined tasks. Record both rival elimination and remaining distinguishing queries. Offer abstention or a query instead of forcing a unique answer. Add parser/DSL conformance and tampered-receipt tests.
3. Factor proposer, selector, oracle and scorer interfaces. Compare same-parent repair to observations only across paired replications; compare Jev to first eligible and random on *identical* proposal sets. Count oracle calls, tokens and invalid outputs, not just successes. Admit DreamCoder/LILO adapters under the same disclosure, representation, and budget rules; separate representational limitations from search failures.
4. Add an independent application oracle and new task families; reserve an unrevealed final evaluation suite. Only then assess transfer or library reuse. Do not equate induced device behavior with application intent.
