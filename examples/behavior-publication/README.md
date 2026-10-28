# Publication: one complete synthetic cutover unit

This example publishes an issue draft, recomputes its identifier and durably
records notification intent. A separate worker delivers the notification.
Everything is synthetic. No FG source, production recording or real provider is
included; this example cannot authorize a production migration.

## Run

From the repository root:

```sh
nix develop .#behavior
uv sync --frozen --group lint
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH=src
python scripts/check-skips.py --allowlist examples/behavior-publication/no-skips.json tests.test_behaviors
capcov behavior check --registry examples/behavior-publication/registry.json \
  --checks examples/behavior-publication/checks.json --scope publication \
  --toolchain /absolute/path/to/toolchain.json --evidence /tmp/publication-evidence --cutover
```

Use a fresh empty evidence directory each run. Without Nix, provide `bifrost`,
`BIFROST_SHEN_SCHEME`, Souffle and Java; use the project's reviewed runtime pins.
The example check plan calls `python` from PATH. Native unit classes run in the
existing Shen and Souffle families.

Copy `toolchain.example.json` to a local toolchain file and set absolute paths to
the pinned ShenCheck checkout, pinned Vör checkout (after `make bootstrap`),
ShenCheck's checksum-pinned TLC jar and Java. Pins are in
`src/capcov/behaviors/shencheck-effects-pins.json`. Obtain the jar with ShenCheck's
`formal/tla/fetch_tool.py`; nixpkgs' pinned `tlaplus` uses the same jar. The engine
is mandatory for this example: missing tools yield unresolved evidence, not a
second workflow to evaluate by hand. The private ShenCheck checkout is not
bundled in capcov or fetched implicitly by CI.

`registry.json` binds the checked-in example, tests and relevant implementation
files by hash. After intentionally changing one, review its affected obligations,
update the enrolled digest and execute fresh evidence. Do not silently regenerate
digests merely to turn a stale gate green. The registry is a maintained fixture,
not a generated authoritative description of an unknown application.

## Files and execution

- `route.json`: closed handler program. Ask for tenant-scoped state, ask for
  authorization, commit publication, return a tagged result.
- `worker.json`: load intent, attempt external delivery, settle only after an
  acknowledged result. An unknown delivery result leaves intent pending.
- `backend.py`: real SQLite transactions for the synthetic domain. Request
  deduplication, authorization recheck, version compare-and-swap, identifier update
  and outbox insertion share one transaction. The provider simulator stores its
  idempotency records separately from settlement.
- `legacy.ops`: intentionally small legacy abstraction run by the existing Shen
  system engine. It models draft-to-published status, not complete legacy semantics.
- `store.md`: the physical, representation, access and domain contracts.
- `registry.json`, `checks.json`: obligations and the commands that exercise them.
- `recovery.json`: an example static claim import, with no invented observation.
- `observe.py`: runs the target and projects actual durable state at commit and
  response into the shared Vör model.
- `shencheck-effects-v1` in `checks.json`: runs the existing ShenCheck/Vör cohort,
  its generated TLA+ checks and the observer, within the same evidence gate.

The target's stronger durable-intent contract is an explicit synthetic decision.
The example comparator input demonstrates its narrow allowed difference. Importing
`recovery.json` creates a changed registry and therefore requires fresh checks.

```sh
capcov behavior compare --registry examples/behavior-publication/registry.json \
  --checks examples/behavior-publication/checks.json --scope publication \
  --toolchain /absolute/path/to/toolchain.json --evidence /tmp/publication-evidence --input examples/behavior-publication/comparison.json
```

The tests exercise successful publication and retry, wrong tenant, denied or
revoked authorization, competing versioned writer, unknown commit result,
conflicting request reuse, ambiguous sentinel, unknown external reply with retry,
correlated checkpoint restore, illegal route effects, incomplete outcomes,
request-checked transcript replay, source invalidation and exact decision scope.

## What the checks mean

The qualification is for these synthetic obligations. The access matrix contains
a **cooperating versioned legacy writer**, not an arbitrary PHP application. A
legacy writer that bypasses the version protocol is outside this example's
assumptions and must block a real cutover until characterized or coordinated.

The integrated protocol lane uses Vör's one-request Boolean effects model. Its
healthy finite state space, certificate controls and four defect models must all
complete under the exact pinned sources. TLA+ is generated from that model;
there is no independent handwritten protocol specification in this example.
The actual publication commit/response prefix is checked against the same model.
The observer covers two boundaries and does not invent observations of worker
leases, tenant-general safety or distributed fencing. General implementation
refinement, translation proofs and liveness remain explicitly OPEN.

The effect transcript is a different check: it supplies recorded replies only
when the requested operation and payload match. It neither executes SQL nor
validates an adapter. The stateful SQLite tests provide that separate, bounded
adapter evidence. Checks that skip because tools are absent fail the example's
qualification rather than passing with an empty test run.
