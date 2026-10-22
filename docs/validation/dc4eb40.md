# Full gate run at dc4eb40 (shen-scheme v0.52-pyrex41.5 on an unmodified build of upstream shen-sources ec16a9f)

Every claim below is about one revision.

| | |
|---|---|
| Revision run | `dc4eb406702b45a389ee1a5e77c8aedc1a9993fd` (branch `feat/shen-scheme-pyrex41.5`) |
| What changed since [031035a](031035a.md) | shen-scheme now builds from fork release [v0.52-pyrex41.5](https://github.com/pyrex41/shen-scheme/releases/tag/v0.52-pyrex41.5) (pyrex41/shen-scheme `680e2e9`). Its kernel is an unmodified build of upstream [Shen-Language/shen-sources `ec16a9f`](https://github.com/Shen-Language/shen-sources/commit/ec16a9fa4fc2e87e2aa336fb1ae30e8ac2266394), the merge of #117, published as [pyrex41/shen-sources release `upstream-ec16a9f`](https://github.com/pyrex41/shen-sources/releases/tag/upstream-ec16a9f). The code is 43.1.2's; `(version)` is `"43.1"`. The v2 manifests are repinned (runtime identity only). |
| Date of run | 2026-10-22, 12:15Z to 12:22Z |
| Platform | macOS 27.0.1, Apple M5, 10 cores, 32 GiB; developer machine, shared with other sessions |
| Nix | Determinate Nix 3.23.2 (Nix 2.35.3); flake ref `path:.` in a detached worktree at the revision, clean before and after |
| Previous report | [`031035a.md`](031035a.md), kept as the record of that revision |
| Roadmap | R01, `docs/production-roadmap.md` §5 (W0) and §2 |

Status words: **executed at dc4eb40**, **not executed (reason)**, **failed**.

## Commands

The same as [1ce541f](1ce541f.md#commands): the CI commands of `.github/workflows/ci.yml`, with each family run as one shard (`--shard 1/1`), flake ref `path:.`, and 4 worker processes per shard (`CAPCOV_TEST_JOBS=4`).
- **Load.** Load average was 6 to 13, the quietest of these runs, so the wall times are lower than in earlier reports.
- **Cache.** The flake checks were already built for this revision, so `nix flake check` took 21 s.

## Unit suite, per family (executed at dc4eb40)

2236 tests discovered; all 2236 ran in exactly one family (partition check passed).

| Family | Status | Ran | Expected failures | Skipped (accepted / unexpected) | Wall s | Result sha256 |
|---|---|---|---|---|---|---|
| base | executed at dc4eb40 | 1885 | 2 | 0 | 60 | `7d955b6208148f81c832028226e13a93ba71d21dd80fd688b16b56336611e592` |
| souffle | executed at dc4eb40 | 165 | 0 | 0 | 141 | `7df4c7ff5f8383fb75d7d8d492bde218fe857508d931dbe6fb7d8ca31a7ac56f` |
| shen (`CAPCOV_SHEN_REQUIRED=1`, shen-scheme) | executed at dc4eb40 | 155 | 4 | 1 (1 / 0) | 105 | `16bd8a31781fa4875036085a76b556a00f6820968d2e6999329d72153d9cb4e8` |
| indexers | executed at dc4eb40 | 31 | 0 | 0 | 7 | `617b0c4069c5ca5a567d4463a599b3da1d852cfbda85e952f7a623a0fe36bdcd` |
| **gate (merge)** | **passed** | 2236 | — | 1 (1 / 0) | — | — |

Verbatim summary lines:

- base: `Ran 1885 tests in 55.584s`, `OK (expected failures=2)`
- souffle: `Ran 165 tests in 138.167s`, `OK`
- shen: `Ran 155 tests in 100.362s`, `OK (skipped=1, expected failures=4)`
- indexers: `Ran 31 tests in 5.329s`, `OK`
- merge: `discovered: 2236; ran across 4 shards: 2236`, then `skipped: 1; accepted by the allowlist: 1`

**Notes.**
- **The accepted skip** is `test_modelcheck.LiveModelTest.test_the_named_model_is_well_formed_at_its_recorded_digest`, which needs `CAPCOV_MODEL_DIR`.
- **Timings.** The regenerated timings are not committed; `tests/shard-timings.json` stays as on `main`.
- **Shen.**
  - The typed authority took typed batch 5.9 s and untyped batch 2.4 s for 3148 units.
  - `RuntimeDifferentialTest` (shen-go beside shen-scheme) took 19.9 s.

## CI test and flake jobs (executed at dc4eb40)

| Step | Status | Wall s |
|---|---|---|
| `check-backpressure.sh` | executed at dc4eb40; passed (its broken controls were blocked) | 20 |
| `check-real-go-flow.sh` | executed at dc4eb40; passed | 9 |
| `check-fault-harness.sh` | executed at dc4eb40; passed (both patched copies rejected) | 9 |
| `ruff check .` | executed at dc4eb40; passed | 2 |
| `uv build` | executed at dc4eb40; passed | 11 |
| `check-wheel.sh dist` | executed at dc4eb40; passed, `RELEASE_REF` unset | 2 |
| `nix flake check` (aarch64-darwin) | executed at dc4eb40; passed: capcov-package, scip-go-index-smoke, shen-evaluator-smoke, shen-package, shen-scheme-smoke, souffle-recursive-typed-smoke | 21 |

### GitHub Actions at dc4eb40

Run [39776839699](https://github.com/pyrex41/capcov/actions/runs/39776839699) on pyrex41/capcov (PR #21), `ubuntu-latest` (x86_64-linux): **success**.

| Job | Result | Duration |
|---|---|---|
| Flake checks | pass | 7m6s |
| Unit suite: base | pass | 3m12s |
| Unit suite: souffle 1/3, 2/3, 3/3 | pass | 2m17s, 2m8s, 4m7s |
| Unit suite: shen 1/1 | pass | 13m37s (cold cache: Chez build for the new store path) |
| Unit suite: indexers | pass | 1m52s |
| Every test ran once (gate) | pass | 52s |
| Check scripts, lint and build | pass | 2m54s |

## shen-scheme v0.52-pyrex41.5

**Builds:**
- aarch64-darwin: `/nix/store/hmayq6j3nmg2rg68r0bkda1i8k58d9h1-shen-scheme-0.52-pyrex41.5`, identity digest `7b175b797ab57c6d1a6b3fbd84eccc10cb1f9f4f0b854f40c992fdda24ed0579` (as in the v2 manifests).
- aarch64-linux: `/nix/store/4h9cdqsn9bym81mzsmxps941nf951dws-shen-scheme-0.52-pyrex41.5`, built and passed `shen-scheme-smoke` natively in a `nixos/nix:2.24.10` container on OrbStack. It prints `λ雪 café` as its 11 bytes.
- x86_64-linux: GitHub Actions, above.

**Inputs:**
- Release tarball: `shen-scheme-v0.52-pyrex41.5-src.tar.gz`, sha256 `c57f47586894534b9797daf5c0cc65c58dc6fb89d6ea6f0c2b48ac64de66d010`.
- Kernel: `ShenOSKernel-43.1-ec16a9f.tar.gz` from release `upstream-ec16a9f`, sha256 `060066a8f84d9a2f7d41cb3b37b986a8d4653279752b739b5063cd648d9baacd`.
  - It is an unmodified build of upstream commit `ec16a9fa4fc2e87e2aa336fb1ae30e8ac2266394`; `(version)` is `"43.1"`.
  - Its `klambda/` is byte-identical to 43.1.2's except `init.kl`, which differs only in the version string. `t-star.kl` is `a1d2fa6f…`, as in 43.1.2.
  - In the release's `compiled/`, only `init.scm` differs from `.4`, and only in the version string.

**Manifests.** `capcov experiment claims spec build` against the aarch64-darwin build moved exactly 4 keys per v2 manifest: `runtime.sha256` and the three `runtime.support` digests. The installed pack, schema and stub files are byte-identical to the rebuild.

**The fork's own gates** (aarch64-darwin, a clean archive of `680e2e9` built with upstream's release recipe):
- `make test`: rc 0. Kernel tests `passed ... 134` / `failed ... 0`, including `(version)` = `"43.1"`; 432 `[OK]` lines.
- `make test-external-runtime`: rc 0.
- Byte-string boundary checks: 7/7 under the Petite runtime too.
- Fork CI at `680e2e9`: macOS, ubuntu and Windows passed.

**The eight shen workloads.** Every payload is byte-identical to shen-go 1f587de for `.5`, both the fork's local build and capcov's nix build. The hashes are those in [1ce541f](1ce541f.md). The b-typed driver had sha256 `335274c4…` before and after every b-typed run.

## Instructions retired: v0.52-pyrex41.4 (43.1.2) against .5 (upstream ec16a9f)

Measured with `/usr/bin/time -l` on each shen-scheme process, using capcov's nix builds of `.4` and `.5`. There were 5 interleaved rounds, alternating which build ran first.
- **Workloads:** run 2026-10-22, 03:51Z to 04:00Z, at load 23 to 39.
- **Typed batch:** run 12:13Z to 12:14Z, at load about 4. It was counted through a wrapper, as in [031035a](031035a.md).

Values are medians of 5 runs. The change is the median of the per-round `.5`/`.4` ratios.

| Workload | `.4` | `.5` | Change | Range |
|---|---|---|---|---|
| a0-bare | 1.923 G | 1.922 G | −0.04% | −0.76% to +0.37% |
| a1-libs-untyped | 4.682 G | 4.678 G | −0.02% | −0.27% to +0.14% |
| a2-libs-typed | 22.49 G | 22.44 G | −0.33% | −0.47% to +0.31% |
| b-typed | 64.95 G | 64.96 G | +0.02% | −0.03% to +0.07% |
| c-untyped | 25.35 G | 25.35 G | −0.03% | −0.03% to +0.04% |
| d-g5 | 180.37 G | 180.46 G | +0.03% | −0.01% to +0.13% |
| e-draft | 8.092 G | 8.087 G | −0.09% | −0.11% to +0.16% |
| f-modelcheck | 2.863 G | 2.862 G | +0.04% | −0.20% to +0.29% |
| typed-authority batch: the typed `script` call | 64.79 G | 64.80 G | −0.03% | −0.06% to +0.08% |
| typed-authority batch: the untyped call | 25.33 G | 25.33 G | −0.02% | −0.07% to +0.06% |
| guard117 `mb-terms` | 67.00 G | 67.01 G | +0.01% | −0.05% to +0.02% |
| guard117 `mb-defs` | 66.47 G | 66.44 G | −0.05% | −0.14% to +0.06% |

- **No difference.** That is what the same code should give. Every workload is within ±0.4%, with identical payloads and exit code 0.
- **The typed-authority test** passed all 4 tests with 3148 units in every run.

## Unresolved

- **One build.** The shen-scheme build is not bit-reproducible, so the manifests' `runtime.sha256` names the aarch64-darwin build above.
- **Not run natively.** The capcov suite was not run on aarch64-linux.
- **Kernel provenance.** The kernel is an unmodified build of an upstream commit, but no Shen-Language release contains `ec16a9f` yet. The tarball is published by pyrex41/shen-sources, not by Shen-Language.
