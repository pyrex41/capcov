# Full gate run at f7c1d3c (shen-scheme pinned to the fork release v0.52-pyrex41.1)

Every claim below is about one revision.

| | |
|---|---|
| Revision run | `f7c1d3c376f5c06973f78fe18656d0798c8fdd04` (branch `feat/shen-runtime-choice`) |
| What changed since [7aa4f75](7aa4f75.md) | shen-scheme now builds from release [v0.52-pyrex41.1](https://github.com/pyrex41/shen-scheme/releases/tag/v0.52-pyrex41.1) of the pyrex41 fork instead of upstream v0.52 plus a patch file; v2 manifests repinned (runtime identity only); CI runs the Shen family as one shard; a check-skips test made robust to worker start-up order |
| Date of run | 2026-10-20, 12:57Z to 13:08Z |
| Platform | macOS 27.0.1, Apple M5, 10 cores, 32 GiB; developer machine, shared with other sessions |
| Nix | Determinate Nix 3.23.2 (Nix 2.35.3); flake ref `path:.` in a detached worktree at the revision, clean before and after |
| Previous report | [`7aa4f75.md`](7aa4f75.md), kept as the record of that revision |
| Roadmap | R01, `docs/production-roadmap.md` §5 (W0) and §2 |

Status words: **executed at f7c1d3c**, **not executed (reason)**, **failed**.

## Commands

The CI commands of `.github/workflows/ci.yml`, with two differences: each family ran as one shard
(`--shard 1/1`) instead of CI's matrix, and the flake ref is `path:.`.

```sh
# per family, one after another; CAPCOV_SHEN_REQUIRED=1 for shen; CAPCOV_SHEN_IMPL unset (default shen-scheme)
nix develop --no-update-lock-file 'path:.#<family>' --command bash -lc \
  "PYTHONPATH=src uv run --frozen --extra probe-python --extra treesitter --extra faults-property \
   --group packaging python scripts/check-skips.py --family <family> --shard 1/1 --result shard-<family>-1-1.json"
# gate job
nix develop --no-update-lock-file 'path:.#base' --command bash -lc \
  'PYTHONPATH=src uv run --frozen ... python scripts/check-skips.py --merge shard-*.json --write-timings shard-timings.json'
# test job, each in .#indexers: check-backpressure.sh, check-real-go-flow.sh, check-fault-harness.sh,
#   ruff check ., uv build, check-wheel.sh dist
nix flake check --no-update-lock-file 'path:.'
```

- Each shard ran its classes in parallel worker processes (`check-skips.py` default `--jobs`, 10 here).
- Load average was 18 to 33, so wall times are upper bounds.

## Unit suite, per family (executed at f7c1d3c)

2236 tests discovered; all 2236 ran in exactly one family (partition check passed).

| Family | Status | Ran | Expected failures | Skipped (accepted / unexpected) | Wall s | Result sha256 |
|---|---|---|---|---|---|---|
| base | executed at f7c1d3c | 1885 | 2 | 0 | 71 | `9556f5bbc8b181b51d852012bd92c85d956160ace42ca4e686f0b29b237de94e` |
| souffle | executed at f7c1d3c | 165 | 0 | 0 | 236 | `30605aa52342e24d1f85ff12b0e9516bccca363c9277033c7ff73a71b88ddea3` |
| shen (`CAPCOV_SHEN_REQUIRED=1`, shen-scheme) | executed at f7c1d3c | 155 | 4 | 1 (1 / 0) | 95 | `674c29b49c9a462e3e4ec489f55ea86f750f23fe44e63431e53c119d2430f1a4` |
| indexers | executed at f7c1d3c | 31 | 0 | 0 | 16 | `63ca321ee43be2270cfa3846fe6bdbf5392719eb8fc4fb18f6d92b54d71437a1` |
| **gate (merge)** | **passed** | 2236 | — | 1 (1 / 0) | — | — |

Verbatim summary lines:

- base: `Ran 1885 tests in 70.706s`, `OK (expected failures=2)`
- souffle: `Ran 165 tests in 235.681s`, `OK`
- shen: `Ran 155 tests in 95.324s`, `OK (skipped=1, expected failures=4)`
- indexers: `Ran 31 tests in 16.131s`, `OK`
- merge: `discovered: 2236; ran across 4 shards: 2236`, then `skipped: 1; accepted by the allowlist: 1`

**Notes.**
- **The accepted skip** is `test_modelcheck.LiveModelTest.test_the_named_model_is_well_formed_at_its_recorded_digest`, which needs `CAPCOV_MODEL_DIR`.
- **Timings.** The regenerated timings file (sha256 `471c9e4d96f451297f84ea2f51c665bcbf64b9ffd1c843f795fe8c8681dc3e1a`) is committed as `tests/shard-timings.json` in the commit that adds this report.
- **The typed authority differential** took 15.6 s (typed batch 11.9 s, untyped batch 3.3 s, 3148 units).
- **G5.** The G5 byte-identity gate took 40.4 s.
- **`RuntimeDifferentialTest`** (shen-go beside shen-scheme) took 31.1 s over its three tests.

## CI test and flake jobs (executed at f7c1d3c)

| Step | Status | Wall s |
|---|---|---|
| `check-backpressure.sh` | executed at f7c1d3c; passed (its broken controls were blocked) | 70 |
| `check-real-go-flow.sh` | executed at f7c1d3c; passed | 29 |
| `check-fault-harness.sh` | executed at f7c1d3c; passed (both patched copies rejected) | 15 |
| `ruff check .` | executed at f7c1d3c; passed | 7 |
| `uv build` | executed at f7c1d3c; passed | 24 |
| `check-wheel.sh dist` | executed at f7c1d3c; passed, `RELEASE_REF` unset | 4 |
| `nix flake check` (aarch64-darwin) | executed at f7c1d3c; passed: capcov-package, scip-go-index-smoke, shen-evaluator-smoke, shen-package, shen-scheme-smoke, souffle-recursive-typed-smoke | 24 |

### GitHub Actions at f7c1d3c

Run [39426259650](https://github.com/pyrex41/capcov/actions/runs/39426259650) on pyrex41/capcov (PR #16), `ubuntu-latest` (x86_64-linux): **success**.

| Job | Result | Duration |
|---|---|---|
| Flake checks | pass | 8m45s |
| Unit suite: base | pass | 3m57s |
| Unit suite: souffle 1/3, 2/3, 3/3 | pass | 3m27s, 2m00s, 4m09s |
| Unit suite: shen 1/1 (one shard) | pass | 11m04s |
| Unit suite: indexers | pass | 1m40s |
| Every test ran once (gate) | pass | 43s |
| Check scripts, lint and build | pass | 2m45s |

**Run history.**
- **Cold-cache Shen shard.** The single Shen shard took 11 minutes, mostly the Chez build for the new store path. The three-shard runs at 7aa4f75 also took 9 to 11 minutes each.
- **The previous revision, `0dc9dd3`, failed CI** (run 39423484165, and again on rerun) in the base shard. `test_check_skips.ParallelShardTest` asserted that more than one of three workers ran a class, and on the loaded runner one worker drained the six tiny fixture classes before the others started.
- **The fix.** `f7c1d3c` holds each fixture class until a second worker has started one. The test passed 8 of 8 concurrent runs locally under load, and in this run.

## shen-scheme builds of this revision

| System | Result |
|---|---|
| aarch64-darwin | `/nix/store/diafx2fxkfidmn4k89xl01bsqq6v86g6-shen-scheme-0.52-pyrex41.1`; identity digest `00395fa3432f8e951de1a14461cc8e409dd9cbf363f2c88d6fc5da19b6ba9c9b` (as in the v2 manifests) |
| aarch64-linux | built and `shen-scheme-smoke` passed natively in a `nixos/nix:2.24.10` container on OrbStack |
| x86_64-linux | built and `shen-scheme-smoke` passed under Rosetta emulation, and natively in GitHub Actions (above) |

The release tarball is `shen-scheme-v0.52-pyrex41.1-src.tar.gz`, sha256 `7708a7c51affa5e729018f649bd61741592e23c2899878751d32b1a73734b931`.

## Tool identities

| Tool | Store path |
|---|---|
| Python 3.14.7 | `/nix/store/k07j8cq0iyvna81qlhwxz8xq6pkz02z8-python3-3.14.7` |
| uv 0.12.5 | `/nix/store/71zq15rr7i4avy58y89hfgf2lhp3b7la-uv-0.12.5` |
| shen-scheme v0.52-pyrex41.1 (default) | `/nix/store/diafx2fxkfidmn4k89xl01bsqq6v86g6-shen-scheme-0.52-pyrex41.1` |
| shen-go (rev `c12933d`, differential) | `/nix/store/xc7f80vh6gb5j6ar0452sflfs8jm1xxm-shen-go-0-unstable-2026-09-14` |
| bifrost (rev `6523641`) | `/nix/store/agfx3svkimxr3mx8653ydnzzrrjf0d4p-bifrost-0-unstable-2026-09-27` |
| Soufflé 2.5 | `/nix/store/hjf84h92h4ynbbn9sg9q1biyr25r617i-souffle-2.5` |
| scip 0.9.0, scip-go 0.2.7, scip-python 0.6.6 | `hckm2075…-scip-0.9.0`, `3inxss33…-scip-go-0.2.7`, `v6h2r1a1…-scip-python-0.6.6` |
| PHP 8.4.25, Go 1.27.0 | `z56wx51l…-php-with-extensions-8.4.25`, `lz3qw52r…-go-1.27.0` |

## Changes since 7aa4f75

- **The shen-scheme pin** moves from upstream v0.52 plus `nix/tools/shen/patches/shen-scheme-byte-strings.patch` to the fork release v0.52-pyrex41.1.
  - The release was made with upstream's own `make source-release` recipe.
  - The patch file and its cache-key entry are gone.
- **v2 manifests repinned** (`dafdfd1`). In each, exactly 4 keys moved: `runtime.sha256` and the three `runtime.support` digests.
  - The executable digest, the implementation, the compiler block, every artifact and bundle digest, and the installed pack files are unchanged.
- **CI Shen shards.** CI runs the Shen family as one shard, not three: it is about 520 s of test time on shen-scheme, and every extra shard repeats a cold Chez build.
- **check-skips test.** `test_check_skips.ParallelShardTest` waits for a second worker instead of racing worker start-up (see above).

## Unresolved

- **`runtime.sha256` names one build.** The shen-scheme build is not bit-reproducible, so the manifests' `runtime.sha256` names the aarch64-darwin build above.
- **Upstream PR.** The byte-strings fix is proposed upstream as a draft, [tizoc/shen-scheme#43](https://github.com/tizoc/shen-scheme/pull/43).
- **Not run natively.** The capcov suite was not run on aarch64-linux.
