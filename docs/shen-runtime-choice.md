# The Shen runtime: shen-scheme (default), shen-go, shen-c

Status: **shen-scheme is the default runtime.**
- It is upstream [tizoc/shen-scheme](https://github.com/tizoc/shen-scheme) v0.52 with one patch, pending upstream.
- shen-go, the earlier runtime, stays selectable and runs beside it as a differential on every suite run.
- shen-c is a third, optional choice.
- [`validation/7aa4f75.md`](validation/7aa4f75.md) holds the full gate run at the switching revision. CI on x86_64-linux passed there too.

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

`nix/tools/shen/shen-scheme.nix` builds the **upstream release source tarball**.
- `shen-scheme-v0.52-src.tar.gz`: tag v0.52 = `fa0717374d907545c997ba0e38526f02b720a2ab`, `sha256-bz1L36hqFeeRYojzIOai+NFzm9xak79w04O57oPIaXQ=`, kernel S43.1.
- It builds on Chez Scheme 10.3.0 (`sha256-0jfZh0xuiwzPd1jaqChqboJVKLE847K8pW6x9zzdvCw=`), the version the Makefile pins (nixpkgs' chez is 10.4.1).

**No bootstrap.**
- The tarball ships the kernel already compiled to Scheme (`compiled/*.scm`, `shen-scheme.scm`, `shen-scheme-runtime.ss`), so the build is Chez plus `make all`.
- No bootstrap Shen and no prebuilt binary. That is what makes aarch64-linux possible.
- The earlier fork pin needed the x86_64-only v0.26 prebuilt, and a shen-go bootstrap produces Scheme that Chez rejects.

**`dontStrip`.** `strip` rewrites the boot files, which then fail Chez's version check.

**Platforms.**

| System | Result |
|---|---|
| aarch64-darwin | package, `shen-scheme-smoke` and the full gate; store path `/nix/store/airvywm27qpxxza8mlhxz5rl8gz5lk4i-shen-scheme-0.52` |
| aarch64-linux | package and `shen-scheme-smoke` built and pass, natively, in a `nixos/nix:2.24.10` container on OrbStack (2 min 50 s) |
| x86_64-linux | natively on GitHub Actions `ubuntu-latest` (run 39348528451 at `7aa4f75`): the flake checks, including `shen-scheme-smoke`, and all three Shen shards passed. With a cold cache, the Shen shards took 9 to 11 min, mostly the Chez build. Earlier, it also built under Rosetta emulation (5 min 31 s). |

Each Linux build prints `λ雪 café` as its own 11 bytes.

**Not reproducible.** `nix build --rebuild` reports differing outputs for every shen-scheme build tried, and for shen-c. A recorded digest names one build; a binary cache keeps it stable.

### The patch, pending upstream

`nix/tools/shen/patches/shen-scheme-byte-strings.patch`: 3 files, 51 insertions and 7 deletions.

**The bug.** Upstream v0.52 double-encodes text outside ASCII.
- The kernel's reader makes one character of each byte of a source file, and the kernel's own `pr` (writer.kl) writes each character back with `write-byte`.
- shen-scheme's faster `pr` override (upstream 95b5e16, 2018, "Override `pr` with a more performant version") writes `(string->utf8 String)` instead.
- So `(pr "λ雪 café")` writes 18 bytes for the literal's 11.
- In capcov that gave a positive certificate with the wrong strings, and a wrong operations result. Both were caught by `TextContractTest` and `test_transport_unicode_quotes_and_determinism`.

**The patch.**
- `pr` writes each character below 256 as that byte. A character at or above 256 (Scheme-side only) is written as UTF-8.
- File names reach the OS as the UTF-8 their bytes hold (`full-path-for-file`), so `load` works from a checkout under a non-ASCII path, as it does on shen-go.
- **The generated line.** The tarball ships the sources precompiled, so the patch also changes the one generated line in `compiled/overrides.scm`. Precompiling the patched `src/overrides.shen` with the v0.52 binary gives that same line; after normalising gensym names, the rest of the tree is identical.
- **Not carried.** The upstream branch's second commit (command-line arguments, `read-file-as-string`, native-compile paths) is not carried: capcov uses none of them.

**Upstream.**
- The same change, with tests, is branch [`upstream/byte-strings`](https://github.com/pyrex41/shen-scheme/tree/upstream/byte-strings) of pyrex41/shen-scheme on top of tizoc `fa07173`. It has not been proposed upstream yet.
- shen-scheme's own suite on aarch64-darwin:

| | `make test` | kernel 43.1 tests | `[OK]` | `make test-external-runtime` |
|---|---|---|---|---|
| v0.52 (fa07173) | rc 0 | `passed ... 134` / `failed ... 0` | 400 | rc 0 |
| + commit 1 (this patch, with tests) | rc 0 | 134 / 0 | 412 | rc 0 |
| + commit 2 (arguments, `read-file-as-string`) | rc 0 | 134 / 0 | 414 | rc 0 |

The new tests fail on v0.52 and pass under the full and the Petite runtimes.

**What else the pyrex41 fork carried, and why capcov does not need it.**
- **REPL stdin-EOF handling:** capcov runs `script` with stdin closed.
- **`*hush*` gating only stdout:** capcov never sets `*hush*`.
- **Kernel 42.2 provenance:** upstream is now on 43.1 natively.
- **Dead-code removal.**

The capcov gate passes on upstream plus the one patch.

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
   - In each of static, replay and observation, exactly 11 keys moved:
     - `runtime.implementation`;
     - `runtime.sha256` (the aarch64-darwin build's identity digest; it replaces a Linux-Nix shen-go hash);
     - the new `runtime.binary_sha256` and `runtime.support`;
     - `compiler` entries for `shen.py`, `modelcheck.py`, `spec/__init__.py` and `shen_runtime.py`, and `souffle/compile.py`, already stale on `main`.
   - Every artifact digest, every bundle digest and `launcher_sha256` are unchanged.
   - The installed `rules-*-v2.json`, `schema_*_v2.json` and `stubs-*-v2.json` are byte-identical to the build output.
3. **Modelcheck facts.** Nothing to re-mint. The committed `model_well_formed` fixtures are synthetic (`checker_binary` all `b`, checker `0.1-pending`), not runtime-minted, and tests mint their facts at run time.
4. **CI.**
   - **Unit suite:** the `shen` shards run in `.#shen`, so under shen-scheme, with shen-go for the differential.
   - **Flake checks:** add `shen-scheme-smoke`.
   - **Cache:** the existing per-job Nix store caches (`nix-community/cache-nix-action`, on GitHub's Actions cache, with no external account) now also key on `nix/**/*.patch`.
   - **Time limits:** the flake job and the Shen shards get 25 minutes instead of 12, for a cold Chez build. A warm cache restores shen-scheme.
   - **Earthfile:** its shen checks include the smoke.
5. **Docs.**
   - development, system-specifications, typed-claim-authority (its shen-go measurements are annotated), the claim_semantics README, and the roadmap Runtime row.
   - `ir-specification.md` names no runtime and needed no change.

## Remaining work

- **Propose the patch upstream.** The draft is ready; opening it needs the owner's OK. When upstream releases the fix, drop the patch and pin the release.
- **Binary cache.** The builds are not bit-reproducible. A binary cache (or reproducible Chez boot files) would let a manifest digest name the build CI uses.
