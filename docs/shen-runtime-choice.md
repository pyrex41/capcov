# The Shen runtime: shen-scheme (default), shen-go, shen-c

Status: **shen-scheme is the default runtime.**
- It is release [v0.52-pyrex41.4](https://github.com/pyrex41/shen-scheme/releases/tag/v0.52-pyrex41.4) of the pyrex41/shen-scheme fork: upstream [tizoc/shen-scheme](https://github.com/tizoc/shen-scheme) `05cf325` (v0.52 plus upstream's own byte-string fix, [#44](https://github.com/tizoc/shen-scheme/pull/44)) plus the fork commits listed in its FORK.md.
- It runs kernel **ShenOSKernel 43.1.2** ([pyrex41/shen-sources release `shen-43.1.2`](https://github.com/pyrex41/shen-sources/releases/tag/shen-43.1.2)): community 43.1 plus [Shen-Language/shen-sources#117](https://github.com/Shen-Language/shen-sources/pull/117), which makes the type checker dereference the checked term once, with the empty-list guard from its review. It takes about 40% off the typed authority. 43.1.2 is not an official Shen-Language release.
- shen-go, the earlier runtime, stays selectable and runs beside it as a differential on every suite run.
- shen-c is a third, optional choice.
- [`validation/`](validation/) holds the full gate runs:
  - [`7aa4f75.md`](validation/7aa4f75.md) at the switch (upstream v0.52 plus a patch file);
  - [`f7c1d3c.md`](validation/f7c1d3c.md) on fork release `.1`;
  - [`8c491b5.md`](validation/8c491b5.md) on `.2` (kernel 43.1 plus a KLambda patch);
  - [`1ce541f.md`](validation/1ce541f.md) on `.3` (kernel 43.1.1);
  - VALIDATION_LINK_4 on `.4` (kernel 43.1.2).

## Selection

`CAPCOV_SHEN_IMPL=shen-scheme|shen-go|shen-c` (unset or empty: `shen-scheme`) selects the runtime at every Shen call site:
- `claims/shen.py`, `claims/modelcheck.py`, and the spec manifest in `claims/spec/__init__.py`;
- `operations/{__init__,native,system}.py`.

The selection lives in `src/capcov/claims/shen_runtime.py`, inside `claims/` so the pack manifests' compiler block hashes it. An unknown name, an unset binary variable or a missing support file is an error. Nothing falls back.

**Launch.**
- Each runtime goes through the pinned bifrost (`6523641`), using that runtime's own adapter (`bifrost run --impl <name> --raw`).
- Typed runs and batches call the binary directly as `{bin} script {file}`.
- The binary is always named explicitly: `BIFROST_SHEN_SCHEME`, `BIFROST_SHEN_GO` or `BIFROST_SHEN_C`.
- Children never inherit `SHEN_SCHEME_HOME`, `SHEN_SCHEME_RUNTIME`, `SHEN_C_HOME` or `SHEN_RC_HOME`.

**Identity.**
- shen-scheme is an executable plus `petite.boot`, `scheme.boot` and `shen-scheme/runtime.so`, which it loads from `../lib/shen-scheme`.
  - All four are hashed; the identity digest is one sha256 over the executable and the sorted support digests.
  - The executable alone identifies nothing: it is the same file across shen-scheme releases.
- shen-go and shen-c are one file each.
- The records:
  - shen-go records keep their pre-selection keys (`shen_go`, `shen_go_sha256`; `LEGACY_SHAPE_IMPL`).
  - Other runtimes are named, with `binary_sha256`, `support_sha256` and `runtime_sha256`.
  - The modelcheck `recheck` requires a certificate's runtime to be the selected one.

**Numbers.** One contract for every runtime: integers below 2^53 in magnitude, and no floats.

| Expression | shen-go | shen-scheme | shen-c |
|---|---|---|---|
| `(+ 9007199254740991 2)` | `9007199254740992` (float64) | `9007199254740993` | `9007199254740993` |
| `(str 3.0)` | `3` | `3` | `3.0` |
| `(str (/ 1 3))` | `0.3333333333333333` | `0.3333333333333333` | `0.333333333333333` |
| `(n->string 955)` | error | λ (written as UTF-8) | error |

- capcov transports only integers below 2^53, and strings as bytes, so none of these differences reach an answer.
- `NumericContractTest` (±(2^53−1), 2^52) and `TextContractTest` (non-ASCII and quoted strings) require Python's certificate under the selected runtime.

## The shen-scheme package

`nix/tools/shen/shen-scheme.nix` builds the **fork release's source tarball**.
- `shen-scheme-v0.52-pyrex41.4-src.tar.gz`: tag `v0.52-pyrex41.4` on fork master `4366e3d0affbfc592b298ab3199ca275c76cb974`, `sha256-GF4UmvOe8eqw23Gg9loUqRG4wu88o3pkJxL4u8LcGq0=` (hex `185e149af39ef1eab0db71a0f65a14a911b8c2ef3ca37a642712f8bbc2dc1aad`), kernel 43.1.2.
- It builds on Chez Scheme 10.3.0 (`sha256-0jfZh0xuiwzPd1jaqChqboJVKLE847K8pW6x9zzdvCw=`), the version the Makefile pins (nixpkgs' chez is 10.4.1).
- No patch file is carried in capcov.

**No bootstrap.**
- The tarball ships the kernel already compiled to Scheme (`compiled/*.scm`, `shen-scheme.scm`, `shen-scheme-runtime.ss`), so the build is Chez plus `make all`.
- No bootstrap Shen and no prebuilt binary, which is what makes aarch64-linux possible.
- A git checkout of the fork has no `compiled/`, so pinning the fork's git revision would need a bootstrap binary again (the only prebuilts are x86_64-linux and macOS). That is why capcov pins the release tarball.

**`dontStrip`.** `strip` rewrites the boot files, which then fail Chez's version check.

**Platforms.**

| System | Result |
|---|---|
| aarch64-darwin | package, `shen-scheme-smoke` and the full gate; store path `/nix/store/jhxgbvbk40mph0qaby8b3srfmf18gm9g-shen-scheme-0.52-pyrex41.4` |
| aarch64-linux | package and `shen-scheme-smoke` built and pass natively in a `nixos/nix:2.24.10` container on OrbStack (`/nix/store/804g0hs6…-shen-scheme-0.52-pyrex41.4`) |
| x86_64-linux | natively in GitHub Actions on `ubuntu-latest`: flake checks, including `shen-scheme-smoke`, and the Shen shard (see the validation report) |

Each build prints `λ雪 café` as its own 11 bytes.

**Not reproducible.** `nix build --rebuild` reports differing outputs for every shen-scheme build tried, and for shen-c. A recorded digest names one build; a binary cache keeps it stable.

### The fork release

**How it was made.**
- The tag `v0.52-pyrex41.<n>` names the upstream release it is based on (0.52) and the fork's release number on it. It matches upstream's `v*.*` tag scheme without taking a name upstream could use.
- Each tarball was made at its tag with upstream's release recipe, the commands of its `release.yml`:
  - `make fetch-kernel`, `make fetch-prebuilt`, `make precompile-with-prebuilt`;
  - `make`, `make test`;
  - `make source-release`, plus `make binary-release` for the attached macOS-arm64 binary.
- It ran locally. The fork's Actions token is read-only, so the tag-triggered release workflow stops at "Create Release".

**`.4` (current pin): fork master `4366e3d`.** It is `.3` with kernel 43.1.2 instead of 43.1.1.
- **Kernel 43.1.2** adds the guard from review on #117: on an empty hypothesis or datatype list, `shen.by-hypothesis` and `shen.search-user-datatypes` fail at once, as in 43.1, instead of copying the checked term.
  - Its KLambda differs from 43.1.1 only in those two defuns of `t-star.kl` (`a1d2fa6f…`) and in the version string; the gensym numbering is unchanged.
  - `make fetch-kernel` checks `ShenOSKernel-43.1.2.tar.gz` against `c7ec855c…`. `(version)` is `"43.1.2"`.
- **Tarball checks:** `compiled/t-star.scm` is byte-identical to the one from a clean build at the tag, and `compiled/init.scm` has `"43.1.2"`.

**`.3`: fork master `839dfac`.**
- **Rebased onto upstream `05cf325`** (since `.2`). Upstream's [#44](https://github.com/tizoc/shen-scheme/pull/44) makes `pr` and `read-file-as-string` byte-exact, so the fork's own commits for those were dropped.
- **Changed rule:** a character at or above 256 follows upstream, so `pr` writes nothing for it, where `.1` wrote UTF-8. capcov transports bytes, so it never makes one.
- **Kept fork commits:**
  - byte strings at the OS boundary: file names, command-line arguments, native compile and load paths;
  - the REPL stdin-EOF exit;
  - `*hush*` gating only stdout;
  - dead-code removal;
  - the Nix flake.
- **Kernel 43.1.1.**
  - `make fetch-kernel` takes `ShenOSKernel-43.1.1.tar.gz` from pyrex41/shen-sources and checks its sha256 (`86448e80…`), as it does for upstream's kernels.
  - 43.1.1 changes `t-star.kl`, which is regenerated from `sources/t-star.shen`, and the version string. Eleven other `.kl` files differ from 43.1 only in gensym numbering.
  - `(version)` is `"43.1.1"`.
- **`.2` carried the same fix differently**, as a KLambda patch to 43.1 (`patches/kernel-43.1/t-star-deref-once.patch`). `.3` replaces it with the released kernel.
- **Tarball checks:**
  - `compiled/` holds 30 files;
  - `compiled/t-star.scm` has the hoisted `-h` defuns, and `compiled/init.scm` has `"43.1.1"`;
  - `compiled/overrides.scm`'s `pr` uses upstream's Latin-1 `shen-string->bytevector` with the fork's stdout-only hush gate.

**shen-scheme's own suite on aarch64-darwin:**

| | `make test` | kernel tests | `[OK]` | `make test-external-runtime` |
|---|---|---|---|---|
| upstream v0.52 (fa07173) | rc 0 | `passed ... 134` / `failed ... 0` | 400 | rc 0 |
| release v0.52-pyrex41.1 (dce21e3) | rc 0 | 134 / 0 | 419 | rc 0 |
| upstream 05cf325 | rc 0 | 134 / 0 | 415 | rc 0 |
| release v0.52-pyrex41.2 (cd32c9b, 43.1 plus patch) | rc 0 | 134 / 0 | 432 | rc 0 |
| release v0.52-pyrex41.3 (839dfac, 43.1.1) | rc 0 | 134 / 0 | 432 | rc 0 |
| release v0.52-pyrex41.4 (4366e3d, 43.1.2) | rc 0 | 134 / 0 | 432 | rc 0 |

- **The fork's own byte-string tests on plain upstream `05cf325`:**
  - **No double encoding remains:** `pr` to stdout and to files is byte-exact.
  - **Still failing** are the boundary checks the fork keeps: an `eval -e` argument, `load` of a non-ASCII path named by a literal, and a file name on disk.
  - **The ≥256 case** differs by design (above).
- **Fork CI at `4366e3d` and `839dfac`:** macOS, ubuntu and Windows passed. At `cd32c9b` (`.2`), macOS could not get a runner.

**The workload payloads.** On the eight shen workloads every payload is byte-identical to shen-go 1f587de for `.1`, `.2`, `.3` and `.4`, both the fork's local builds and capcov's nix builds.

**Timing** (aarch64-darwin, interleaved rounds, load 20–55):

| Measure | `.1` (43.1) | `.2` (43.1 plus patch) | `.3` (43.1.1) |
|---|---|---|---|
| capcov typed-authority batch, 3 rounds at load ~20 | 13.4, 9.8, 10.6 s | 7.4, 5.6, 6.6 s | 7.7, 5.3, 6.7 s |
| b-typed CPU, 4 runs (capcov nix builds) | 10.09, 9.82, 10.18, 9.69 s | — | 5.93, 5.94, 5.46, 5.46 s |

- **Medians:** the typed batch drops 37% (10.6 → 6.7 s) and b-typed CPU 43% (9.95 → 5.70 s).
- **`.2` and `.3` are the same** within noise, as expected for the same fix.
- **d-g5:** no difference between `.2` and `.3` in instructions retired: the median is −0.05%, over 6 interleaved pairs of capcov's nix builds.
  - CPU time at load 22–41 cannot settle it: the median `.3`/`.2` CPU ratio was +9% in one run and −3.5% in the next.
  - The two kernels differ only in gensym numbering and `*version*` ([validation/1ce541f.md](validation/1ce541f.md)).

**`.3` against `.4`, instructions retired** (`/usr/bin/time -l` on each shen-scheme process, capcov's nix builds, 5 interleaved rounds alternating the order):

| Workload | `.3` (43.1.1) | `.4` (43.1.2) | `.4`/`.3`, median of pairs |
|---|---|---|---|
| b-typed | 65.01 G | 65.04 G | −0.02% |
| d-g5 | 180.45 G | 180.46 G | −0.04% |
| a0-bare | 1.930 G | 1.923 G | −0.37% |
| capcov typed-authority batch (the typed `script` call) | 64.79 G | 64.74 G | −0.07% |
| guard117 `mb-terms`: `shen.typecheck` with no hypotheses and no datatypes | 99.53 G | 67.06 G | **−32.6%** |
| guard117 `mb-defs`: 400 loads of 25 typed defines | 66.58 G | 66.57 G | −0.03% |

- **Medians** of 5 runs each. On every capcov workload `.4` is within ±0.4% of `.3`, with identical payloads.
- **The guard pays off** only when a typecheck starts with no hypothesis or no datatype. That is where 43.1.1 copied the term for nothing; `mb-terms` is built for that case.

## shen-c

- **Pin:** pyrex41/shen-c `05a84f1d5296fdd0bb5202cfe875c986f9836607` (`sha256-h2//wgpBfZXo6H9I7eOMYjfZs5e1mp/VdByf5D9JgTQ=`), one self-contained binary. It is in the `.#shen-runtimes` dev shell only.
- **Platforms:** it builds on aarch64-darwin and aarch64-linux.
- **Results:** correct on everything measured. It is only modestly faster than shen-go on the typed authority, so it remains a fallback.

## Measurements

### Before the switch (revision `60ecbf5`)

The `shen` family, one shard, `CAPCOV_SHEN_REQUIRED=1`, one runtime at a time. The macOS 27 / Apple M5 host was shared (load 18 to 28), so wall times are upper bounds.

| Runtime | Ran | Failed | Skipped | Expected failures | Shard s | Typed differential s (typed batch / untyped batch) | G5 byte-identity |
|---|---|---|---|---|---|---|---|
| shen-go | 152 | 0 | 1 | 4 | 375.3 | 364.4 (355.4 / 8.6) | pass (114.6 s) |
| shen-scheme (fork `fef4b09`, same fix) | 152 | 0 | 1 | 4 | 86.2 | 17.4 (14.1 / 2.6) | pass (32.9 s) |
| shen-c | 152 | 0 | 1 | 4 | 276.9 | 273.0 (218.6 / 54.0) | pass (52.0 s) |

- Typed authority verdicts were identical on all three: 3148 units and the same disagreement set.
- Before the fix (fork `d037ae6`), shen-scheme failed the 3 text tests.

### At the switch (revision `7aa4f75`)

The full gate passed ([validation/7aa4f75.md](validation/7aa4f75.md)):

| Family | Summary |
|---|---|
| base | `Ran 1885 tests in 59.690s`, `OK (expected failures=2)` |
| souffle | `Ran 165 tests in 163.989s`, `OK` |
| shen (shen-scheme) | `Ran 155 tests in 64.419s`, `OK (skipped=1, expected failures=4)`; typed differential 13.6 s (typed batch 10.8 s / untyped 2.6 s) |
| indexers | `Ran 31 tests in 3.808s`, `OK` |
| merge | 2236 of 2236 ran once; 1 accepted skip |

The CI scripts, ruff, `uv build`, `check-wheel.sh` and `nix flake check` all passed. GitHub Actions on x86_64-linux was green.

Since the switch, every suite run checks both runtimes:
- the `shen` family runs under shen-scheme;
- `RuntimeDifferentialTest` re-runs shen-go beside it on:
  - authority over go_app (verdicts, elaboration, checksum);
  - certificates for go_app rows and the numeric and text bundles;
  - a G5 system evaluation (outbox).

## What the switch changed

1. **`DEFAULT_IMPL = "shen-scheme"`.** The `shen` dev-shell family carries shen-scheme and shen-go.
2. **The v2 pack manifests**, repinned with the documented `capcov experiment claims spec build` path:
   - At the switch (upstream v0.52 plus a patch), in each of static, replay and observation, exactly 11 keys moved:
     - `runtime.implementation`;
     - `runtime.sha256` (the aarch64-darwin build's identity digest; it replaces a Linux-Nix shen-go hash);
     - the new `runtime.binary_sha256` and `runtime.support`;
     - `compiler` entries for `shen.py`, `modelcheck.py`, `spec/__init__.py` and `shen_runtime.py`, and `souffle/compile.py`, already stale on `main`.
   - Every artifact digest, every bundle digest and `launcher_sha256` are unchanged.
   - The installed `rules-*-v2.json`, `schema_*_v2.json` and `stubs-*-v2.json` are byte-identical to the build output.
   - At the move to the fork release (`dafdfd1`), exactly 4 keys moved in each manifest: `runtime.sha256` and the three `runtime.support` digests. The executable digest, the implementation, the compiler block, every artifact and bundle digest, and the installed pack files are unchanged.
   - At the move to `.2` (`e64a668`), and again at `.3` (`44f4bcb`), the same 4 keys moved and nothing else. The changed type checker elaborates exactly what it did before.
3. **Modelcheck facts.** Nothing to re-mint. The committed `model_well_formed` fixtures are synthetic (`checker_binary` all `b`, checker `0.1-pending`), not runtime-minted, and tests mint their facts at run time.
4. **CI.**
   - **Unit suite:** the `shen` shards run in `.#shen`, so under shen-scheme, with shen-go for the differential.
   - **Flake checks:** add `shen-scheme-smoke`.
   - **Cache:** the existing per-job Nix store caches (`nix-community/cache-nix-action`, on GitHub's Actions cache, with no external account) key on `flake.lock` and `**/*.nix`. shen-scheme's pin lives in `nix/tools/shen/shen-scheme.nix`, so a new release invalidates them.
   - **Time limits:** the flake job and the Shen shard get 25 minutes instead of 12, for a cold Chez build. A warm cache restores shen-scheme.
   - **Shards:** the Shen family runs as **one** shard. On shen-scheme it is about 520 s of test time, less than souffle's 730 s over 3 shards. Several shards would each repeat the cold Chez build. `tests/shard-timings.json` is regenerated from the gate run.
   - **Earthfile:** its shen checks include the smoke.
5. **Docs.**
   - development, system-specifications, typed-claim-authority (its shen-go measurements are annotated), the claim_semantics README, and the roadmap Runtime row.
   - `ir-specification.md` names no runtime and needed no change.

## Remaining work

- **Upstream.**
  - tizoc merged his own byte-string fix (#44), and our draft #43 is closed.
  - The fork still differs from upstream at the OS boundary and in its kernel (43.1.2 instead of 43.1).
  - If upstream releases the boundary conversions and a kernel release contains Shen-Language/shen-sources#117, capcov can pin an upstream release again.
- **Fork releases.** Each upstream release needs a fork rebase and a new `v<upstream>-pyrex41.<n>` release before capcov can follow it.
- **Binary cache.** The builds are not bit-reproducible. A binary cache (or reproducible Chez boot files) would let a manifest digest name the build CI uses.
