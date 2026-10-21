# The Shen runtime: shen-scheme (default), shen-go, shen-c

Status: **shen-scheme is the default runtime.**
- It is release [v0.52-pyrex41.2](https://github.com/pyrex41/shen-scheme/releases/tag/v0.52-pyrex41.2) of the pyrex41/shen-scheme fork: upstream [tizoc/shen-scheme](https://github.com/tizoc/shen-scheme) `05cf325` (v0.52 plus upstream's own byte-string fix, [#44](https://github.com/tizoc/shen-scheme/pull/44)) plus the fork commits listed in its FORK.md.
- One of those is a kernel patch that makes the type checker dereference the checked term once ([Shen-Language/shen-sources#117](https://github.com/Shen-Language/shen-sources/pull/117)). It takes about 40% off the typed authority.
- shen-go, the earlier runtime, stays selectable and runs beside it as a differential on every suite run.
- shen-c is a third, optional choice.
- [`validation/`](validation/) holds the full gate runs:
  - [`7aa4f75.md`](validation/7aa4f75.md) at the switch (upstream v0.52 plus a patch file);
  - [`f7c1d3c.md`](validation/f7c1d3c.md) on fork release `.1`;
  - [`8c491b5.md`](validation/8c491b5.md) on fork release `.2`.

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
- `shen-scheme-v0.52-pyrex41.2-src.tar.gz`: tag `v0.52-pyrex41.2` on fork master `cd32c9b60ba0659466bd5e6182cdeca9a783ad9a`, `sha256-R9ipObeFxSF6wOPn3oHF2+Jf+itwPLRWJx6SH+AEzac=` (hex `47d8a939b785c5217ac0e3e7de81c5dbe25ffa2b703cb456271e921fe004cda7`), kernel S43.1 with the type-checker patch.
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
| aarch64-darwin | package, `shen-scheme-smoke` and the full gate; store path `/nix/store/91fsxyc7adlr45dv9k0xhvk6qdq5z838-shen-scheme-0.52-pyrex41.2` |
| aarch64-linux | package and `shen-scheme-smoke` built and pass natively in a `nixos/nix:2.24.10` container on OrbStack (`/nix/store/fnrkjkn2…-shen-scheme-0.52-pyrex41.2`) |
| x86_64-linux | natively in GitHub Actions on `ubuntu-latest`: flake checks, including `shen-scheme-smoke`, and the Shen shard (see the validation report) |

Each build prints `λ雪 café` as its own 11 bytes.

**Not reproducible.** `nix build --rebuild` reports differing outputs for every shen-scheme build tried, and for shen-c. A recorded digest names one build; a binary cache keeps it stable.

### The fork release

**How it was made.**
- The tag `v0.52-pyrex41.<n>` names the upstream release it is based on (0.52) and the fork's release number on it. It matches upstream's `v*.*` tag scheme without taking a name upstream could use.
- Each tarball was made at its tag with upstream's release recipe, the commands of its `release.yml`:
  - `make fetch-kernel` (in the fork, it also applies and sha-checks the kernel patch), `make fetch-prebuilt`, `make precompile-with-prebuilt`;
  - `make`, `make test`;
  - `make source-release`, plus `make binary-release` for the attached macOS-arm64 binary.
- It ran locally. The fork's Actions token is read-only, so the tag-triggered release workflow stops at "Create Release".

**`.2` (current pin): fork master `cd32c9b`.**
- **Rebased onto upstream `05cf325`.** Upstream's [#44](https://github.com/tizoc/shen-scheme/pull/44) makes `pr` and `read-file-as-string` byte-exact, so the fork's own commits for those were dropped.
- **Changed rule:** a character at or above 256 follows upstream, so `pr` writes nothing for it, where `.1` wrote UTF-8. capcov transports bytes, so it never makes one.
- **Kept fork commits:**
  - byte strings at the OS boundary: file names, command-line arguments, native compile and load paths;
  - the REPL stdin-EOF exit;
  - `*hush*` gating only stdout;
  - dead-code removal;
  - the Nix flake.
- **New: the kernel patch** `patches/kernel-43.1/t-star-deref-once.patch` (Shen-Language/shen-sources#117).
  - `shen.search-user-datatypes` and `shen.by-hypothesis` dereference the checked term once per call, not once per datatype rule or hypothesis.
  - `make fetch-kernel` applies it and checks the patched `t-star.kl` (`a0cedbb0…`).
- **Tarball checks:**
  - `compiled/` holds 30 files;
  - `compiled/t-star.scm` has the hoisted `-h` defuns;
  - `compiled/overrides.scm`'s `pr` uses upstream's Latin-1 `shen-string->bytevector` with the fork's stdout-only hush gate.

**shen-scheme's own suite on aarch64-darwin:**

| | `make test` | kernel 43.1 tests | `[OK]` | `make test-external-runtime` |
|---|---|---|---|---|
| upstream v0.52 (fa07173) | rc 0 | `passed ... 134` / `failed ... 0` | 400 | rc 0 |
| release v0.52-pyrex41.1 (dce21e3) | rc 0 | 134 / 0 | 419 | rc 0 |
| upstream 05cf325 | rc 0 | 134 / 0 | 415 | rc 0 |
| release v0.52-pyrex41.2 (cd32c9b) | rc 0 | 134 / 0 | 432 | rc 0 |

- **The fork's own byte-string tests on plain upstream `05cf325`:**
  - **No double encoding remains:** `pr` to stdout and to files is byte-exact.
  - **Still failing** are the boundary checks the fork keeps: an `eval -e` argument, `load` of a non-ASCII path named by a literal, and a file name on disk.
  - **The ≥256 case** differs by design (above).
- **Fork CI at `cd32c9b`:** ubuntu and Windows passed. The macOS job was cancelled twice after 15 minutes waiting for a runner, so it is not executed.

**The workload payloads.** On the eight shen workloads every payload is byte-identical to shen-go 1f587de for `.1`, `.2` (local build), and `.2` (capcov's nix build).

**Timing, `.1` against `.2`** (aarch64-darwin, load 30–55, interleaved rounds):
- **b-typed CPU:** median about 8.8 s against 4.7 s (−46%).
- **capcov's typed authority batch:** 11.7/13.0/15.2 s against 7.8/7.9/9.8 s (median −39%).
- **d-g5:** CPU ranged 13.2–16.5 s against 15.7–16.9 s. The ranges overlap, so a change of up to about 10% is within noise and not established.

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
   - At the move to `.2` (`e64a668`), the same 4 keys moved and nothing else. The patched type checker elaborates exactly what it did before.
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
  - The fork still differs from upstream at the OS boundary and in the kernel patch.
  - If upstream releases the boundary conversions and a kernel release contains Shen-Language/shen-sources#117, capcov can pin an upstream release again.
- **Fork releases.** Each upstream release needs a fork rebase and a new `v<upstream>-pyrex41.<n>` release before capcov can follow it.
- **Binary cache.** The builds are not bit-reproducible. A binary cache (or reproducible Chez boot files) would let a manifest digest name the build CI uses.
