# Choosing the Shen runtime: shen-go, shen-scheme or shen-c

Status: **proposal; shen-go stays the default.** This branch makes the runtime
selectable and measures the alternatives. It does not change the default, the
v2 pack manifests or any recorded evidence.

**Current state**
- shen-scheme is pinned to pyrex41/shen-scheme#11 (`fef4b09`).
- That PR fixes the one defect that made shen-scheme give wrong answers: double-encoded non-ASCII output.
- With it, the whole `shen` family passes under shen-scheme, and its typed authority differential is about 21× faster than shen-go's.

## What changed

* `CAPCOV_SHEN_IMPL=shen-go|shen-scheme|shen-c` (unset or empty: `shen-go`)
  selects the runtime at every Shen call site:
  - `claims/shen.py`;
  - `claims/modelcheck.py`;
  - the spec manifest in `claims/spec/__init__.py`;
  - `operations/{__init__,native,system}.py`.

  The selection lives in `src/capcov/shen_runtime.py`. An unknown name, an unset
  binary variable or a missing support file is an error. Nothing falls back.
* Each runtime is launched through the pinned bifrost (`6523641`), using that
  runtime's own adapter (`bifrost run --impl <name> --raw`). Typed runs and
  batches call the binary directly as `{bin} script {file}`.
  - The binary is always named explicitly with `BIFROST_SHEN_GO`,
    `BIFROST_SHEN_SCHEME` or `BIFROST_SHEN_C`, so bifrost never resolves one of
    its default paths.
  - Children never inherit `SHEN_SCHEME_HOME`, `SHEN_SCHEME_RUNTIME`,
    `SHEN_C_HOME` or `SHEN_RC_HOME`.
* **Runtime identity.**
  - shen-go and shen-c are each one self-contained executable, and the record
    hashes it.
  - shen-scheme is an executable plus `petite.boot`, `scheme.boot` and
    `shen-scheme/runtime.so`, which it loads from `../lib/shen-scheme`. All four
    are hashed. The record's identity digest is one sha256 over the executable
    and the sorted support digests.
  - For shen-go, every record keeps its earlier keys and bytes. Other runtimes
    are named in the record:
    - `Runtime.as_dict` (`impl`, `binary_sha256`, `support_sha256`,
      `runtime_sha256`);
    - the modelcheck certificate. Its `recheck` requires the exact key set of
      the recorded runtime, and requires that runtime to be the selected one,
      as it required shen-go before;
    - the spec manifest (`implementation`, `sha256` = identity digest);
    - the operations evidence (`runtime_impl`, and `runtime.impl`).
* **Numbers.** The transport contract is the same for every runtime: integers
  below 2^53 in magnitude, and no floats. Probed directly:

  | Expression | shen-go | shen-scheme | shen-c |
  |---|---|---|---|
  | `(+ 9007199254740991 2)` | `9007199254740992` (float64) | `9007199254740993` | `9007199254740993` |
  | `(str 3.0)` | `3` | `3` | `3.0` |
  | `(str (/ 1 3))` | `0.3333333333333333` | `0.3333333333333333` | `0.333333333333333` |

  - Widening the contract for the exact runtimes would make an answer depend on
    the runtime.
  - The Shen side does no arithmetic on transported values beyond comparison;
    the checksum lanes stay below 2^33.
  - `test_shen_runtime_choice.NumericContractTest` derives rows at ±(2^53−1)
    and 2^52 and requires the Python certificate. It passes on all three.
* **Nix.** shen-scheme and shen-c are packages (`.#shen-scheme`, `.#shen-c`)
  and ship in a new dev shell, `.#shen-runtimes` (the shen family plus both).
  - They are not in the `shen` family, so the unit-suite jobs are unchanged.
  - `checks` gains `shen-scheme-smoke`, which builds shen-scheme (Chez from
    source) in the flake-check job on x86_64-linux and aarch64-darwin.
  - The pins are below.

## Pins

| Runtime | Source | Build inputs (fixed-output) | Store path (aarch64-darwin) |
|---|---|---|---|
| shen-go (default, unchanged) | pyrex41/shen-go `c12933d` | — | `/nix/store/xc7f80vh6gb5j6ar0452sflfs8jm1xxm-shen-go-0-unstable-2026-09-14` |
| shen-scheme | pyrex41/shen-scheme `fef4b0906022b495586957a3132de5e84125b547` (branch `fix/pr-byte-strings`, [PR #11](https://github.com/pyrex41/shen-scheme/pull/11), on master `4dc9cc2`), `sha256-JVu7kg4g453VQ0RN7JxHVZPqgBR9Qi/uCYgQjAUqSyI=` | ShenOSKernel-43.1 `sha256-kA7t70T0QK94+Tle0G5onOFgRUb8MJ9bx8i8hMxlGSA=`; Chez 10.3.0 `sha256-0jfZh0xuiwzPd1jaqChqboJVKLE847K8pW6x9zzdvCw=`; prebuilt shen-scheme v0.26 (precompiles the kernel) macOS `sha256-qcMhooba81TdqKtR6ysZHL3DOcIIfkSQSIyIzkYvXcY=`, linux (x86_64) `sha256-KFk4TzsWzWz1lghM//fi2dWzGhHfPR98nh8XRu1u95g=` | `/nix/store/h6zf93jsy8i7d3md5fr9yjsy8ihqz842-shen-scheme-0-unstable-2026-10-19` |
| shen-c | pyrex41/shen-c `05a84f1d5296fdd0bb5202cfe875c986f9836607`, `sha256-h2//wgpBfZXo6H9I7eOMYjfZs5e1mp/VdByf5D9JgTQ=` | — | `/nix/store/lb0dxscsxzj3bn1ak1248qib1hyscg5l-shen-c-0.3.0-unstable-2026-10-19` |

**shen-scheme revision**
- The first measurements (below, "before the fix") used `d037ae6` (kernel 42.2).
- The fork's default branch has since moved one commit, `4dc9cc2` "Upgrade Shen/Scheme fork to ShenOSKernel 43.1", which:
  - changes the kernel to 43.1, adding the expand-dynamic and type-annotations extensions;
  - adds 43.1 character-stream support (`char-stream?`, `read-unit-string`, `write-string` on textual ports).
- The fix branches from it, so the pin now runs kernel 43.1, where shen-go is S42.
- The whole family, typed authority and G5 included, gives the same answers on it.

**The fix (pyrex41/shen-scheme#11)**
- **Byte strings.** Strings are byte strings, as the kernel's reader builds them and as shen-go and shen-c treat them.
  - `pr` writes a character below 256 as that byte.
  - A character at or above 256, which only Scheme-side code can make, is written as UTF-8. shen-go and shen-c reject `(n->string 955)` instead.
  - capcov never makes such a character: it transports bytes.
- **Boundaries.** File names, command-line arguments and `read-file-as-string` convert at the boundary to the OS.
- **Tests.** `make test-byte-strings` is part of `make test`.
- **shen-scheme's own suite**, on aarch64-darwin, before → after: `make test` rc 0 → rc 0; kernel tests `passed ... 134` / `failed ... 0` both times; 383 → 397 `[OK]`; `make test-external-runtime` rc 0 → rc 0.
- **Reach of the new tests.** They fail on `4dc9cc2` and pass under both the full and the Petite runtime.
- **Same build tested.** The suite ran on a build from a clean `git archive` of `fef4b09`. Its `compiled/*.scm` are byte-identical to the nix build's.

**shen-scheme build**
- **Recipe.** It is upstream's own: `fetch-kernel fetch-prebuilt precompile-with-prebuilt all`.
  - The three downloads are fetches carrying the Makefile's checksums.
  - Chez 10.3.0 is built from source (nixpkgs' chez is 10.4.1).
  - `share/shen-scheme/compiled.sha256` records the precompiled sources.
- **The executable proves nothing.** It is the same file (`b94c9d65…`) at `d037ae6` and at `fef4b09`: it is only the C launcher. That is why the runtime identity also hashes the boot files and `runtime.so`.
- **No shen-go bootstrap.** Precompiling with the pinned shen-go produces sources that Chez rejects (`invalid sharp-sign prefix #-` while compiling the runtime): its symbol escaping differs.
- **`dontStrip` is required.** `strip` rewrites the boot files, which then fail Chez's version check.
- **Linux.**
  - **x86_64-linux** builds (prebuilt patched with `autoPatchelf`, `libuuid`). It ran in a `nixos/nix:2.24.10` `linux/amd64` container under Rosetta, with `filter-syscalls = false`, because Rosetta cannot load nix's seccomp filter.
    - Package and `shen-scheme-smoke` built in 7 min.
    - The smoke check passes, and the binary prints `λ雪 café` as its own 11 bytes.
    - Its `compiled/*.scm` are byte-identical to aarch64-darwin's.
    - This is emulation, not a native CI runner.
  - **aarch64-linux is not supported.** The only Linux prebuilt is x86_64. The package, the smoke check and the dev-shell entry are omitted there by `meta.platforms`.
  - A source release of the fork that carries the precompiled sources (as upstream's release tarballs do) would remove the bootstrap binary on every platform.

**shen-c build**
- **Build.** `make` with clang and no pkg-config, as in shen-c's own flake. Its test suite is not run here.
- **Runs standalone.** The installed `shen-c` runs with an empty environment.
- **Linux.** It also builds on aarch64-linux (container, native arm64) and prints the same bytes.

**Not reproducible**
- `nix build --rebuild` reports that the shen-scheme (`d037ae6` build) and shen-c outputs differ between two builds of the same derivation on this host.
- The `fef4b09` build differs on rebuild too.
- A recorded runtime digest is therefore stable only for one build or through a binary cache.
- Whether the pinned shen-go build is reproducible was not checked.

Runtime file digests (aarch64-darwin, this build):

| File | sha256 |
|---|---|
| shen-go `bin/shen` | `6660a921980e471f6c3cca5b2ebe911c55212678a31a6dde63d7c1a9b3f148c9` |
| shen-scheme `bin/shen-scheme` | `b94c9d6578b0d9fd133836b1e09a15b8c73f9634270c3039159e846c06d55100` |
| shen-scheme `lib/shen-scheme/petite.boot` | `3c5544105158b0596203bd5a1fd48ddeb1a7a19de85e7a1cf15842e21e8b701d` |
| shen-scheme `lib/shen-scheme/scheme.boot` | `4644854a8ec27509ade2779f17b31f8d6fc2b611bae8c9a1b453ebcf7fcb962a` |
| shen-scheme `lib/shen-scheme/shen-scheme/runtime.so` | `78141b7681371dc9fded1513a8aa97ed76f552da035e028081e1d8b543fa7ea5` |
| shen-scheme identity digest | `e8cd5acd771d2159edcb4c662e28f9a3d48c8acc4eda66041923fc17c1fa55dd` |
| shen-c `bin/shen-c` | `ca4dce70828afb2d27e4b44ba6397fb64b5f593e5d89634378a30d5a136267ee` |

## Measured: the `shen` family under each runtime

**Run conditions**
- **Revision:** `60ecbf5`, 2026-10-19, one shard (`--shard 1/1`), `CAPCOV_SHEN_REQUIRED=1`.
- **Host:** the macOS 27 / Apple M5 host of the [e5bf644 report](validation/e5bf644.md).
- **Load:** the host was shared with other sessions, with load average 18 to 28, so wall times are upper bounds.
- **Order:** runtimes ran one after another.

```sh
nix develop --no-update-lock-file 'path:.#shen-runtimes' --command bash -lc \
  "export CAPCOV_SHEN_REQUIRED=1 CAPCOV_SHEN_IMPL=<impl>; \
   PYTHONPATH=src uv run --frozen --extra probe-python --extra treesitter --extra faults-property \
   --group packaging python scripts/check-skips.py --family shen --shard 1/1 --result shard-shen-1-1.json"
```

| Runtime | Ran | Failed | Skipped | Expected failures | Shard s | Typed differential s (typed batch / untyped batch) | G5 byte-identity |
|---|---|---|---|---|---|---|---|
| shen-go | 152 | 0 | 1 | 4 | 375.3 | 364.4 (355.4 / 8.6) | pass (114.6 s; bridge 33.3 s) |
| shen-scheme (`fef4b09`) | 152 | **0** | 1 | 4 | 86.2 | 17.4 (14.1 / 2.6) | pass (32.9 s; bridge 9.9 s) |
| shen-c | 152 | 0 | 1 | 4 | 276.9 | 273.0 (218.6 / 54.0) | pass (52.0 s; bridge 14.8 s) |

Summary lines, verbatim:
- shen-scheme: `Ran 152 tests in 86.194s`, then `OK (skipped=1, expected failures=4)`.
- shen-go: `Ran 152 tests in 375.311s`, then `OK (skipped=1, expected failures=4)`.
- shen-c: `Ran 152 tests in 276.877s`, then `OK (skipped=1, expected failures=4)`.

Result sha256:
- shen-go `2a43580ec53dc1bdedaa2ae1a3d0a3ec023c2a1f195b9ba80c74ec78437add0a`
- shen-scheme `3f78dfe66769442aa3ee0f920c3dec458bee3c51e9168bff6eb27547451c7599`
- shen-c `f74f706fec6524581f46b8d073a013ba75577d75d48484cc5de3caae76611309`

Notes:
- The skip is the accepted one (`LiveModelTest` needs `CAPCOV_MODEL_DIR`).
- The 152 tests are the 148 of the e5bf644 report plus the four live tests this branch adds.
- Typed authority results were identical on all three runtimes: 3148 units, the same disagreement set and the same verdicts.
- `TextContractTest` and `NativeOperationTests.test_transport_unicode_quotes_and_determinism` were also run on their own under all three runtimes: OK each time.

**Before the fix**, at `a541e7d` with shen-scheme `d037ae6`:

| Runtime | Ran | Failed | Shard s | Typed differential s | G5 |
|---|---|---|---|---|---|
| shen-go | 152 | 0 | 327.8 | 324.1 | pass |
| shen-scheme `d037ae6` | 152 | **3** | 109.9 | 19.5 | pass |
| shen-c | 152 | 0 | 292.0 | 289.8 | pass |

The standalone benchmark of the typed-authority workload agrees in shape: shen-go `c12933d` took a median of 231 s and shen-scheme 7.0 s.

### Divergences, classified

**At `fef4b09`:** none in the `shen` family.

The remaining differences are outside capcov's contract, and the transport keeps them out:

| Behaviour | shen-go | shen-scheme | shen-c | capcov |
|---|---|---|---|---|
| integers past 2^53 | float64, rounds | exact | exact | refused before transport |
| `(str 3.0)` | `3` | `3` | `3.0` | floats refused |
| `(n->string 955)` | error | U+03BB, printed as UTF-8 | error | never sent: strings travel as bytes |

**At `d037ae6`**, all three shen-scheme failures had one cause:
- **The failures.**
  - The operations unicode test got `issue-"\⏎Î»é›ª` back for `issue-"\⏎λ雪`.
  - `TextContractTest` received a *positive certificate with double-encoded strings*, not a refusal.
- **The mechanism.**
  - The kernel's reader builds strings byte by byte.
  - The `pr` override then wrote binary ports with `string->utf8`, which encoded each byte above 127 a second time.
- **Fix.** pyrex41/shen-scheme#11 (above).

No shen-c divergence was found at `05a84f1`. The benchmark's DIFFERS on c-untyped, d-g5 and e-draft were measured at `802e724`. The benchmark itself was not re-run at `05a84f1`, but the family tests that cover those paths pass there.

**Test changes.** Tests that hardcoded shen-go now follow the selected runtime:
- `test_shen_transport`;
- `test_modelcheck` (the certificate keys, the preflight);
- `test_typed_authority.ForgedTypedIRTest`;
- `test_ir_specification.DraftTypecheckTest`.

`FakeLauncherFailureTest` tests the transport, not a runtime. It pins `CAPCOV_SHEN_IMPL=shen-go` around its fake binary.

## What switching the default would take

1. **Merge pyrex41/shen-scheme#11** and repin to the merged commit.
   - The suite and this family must be re-run at that commit, since the pin is now a branch head.
   - Decide whether kernel 43.1 (which the fix sits on) is acceptable, or backport the fix onto `d037ae6` for 42.2.
2. **Make it hermetic on CI.**
   - Add shen-scheme to the `shen` family (`packages`, `BIFROST_SHEN_SCHEME`).
   - `shen-scheme-smoke` is already in `checks`. On ubuntu-latest (x86_64-linux) it builds Chez from source: about 7 min under emulation here, and not yet run on a GitHub runner.
   - **aarch64-linux** has no bootstrap. It needs a fork source release with precompiled sources, or must stay unsupported.
   - The build is not bit-reproducible. Before a manifest records its digest, make it reproducible or serve it from a pinned binary cache.
3. **Flip `shen_runtime.DEFAULT_IMPL`.** Every record then names shen-scheme.
   - Records that used to say `shen_go`/`shen_go_sha256` now say `binary`/`binary_sha256` plus `support_sha256`.
   - `modelcheck.recheck` refuses a certificate from a runtime other than the selected one, so existing shen-go certificates must be re-minted (step 6).
4. **Repin the v2 pack manifests in one deliberate commit**
   (`src/capcov/claims/{static,replay,observation}/rules-*-v2.manifest.json`):
   - `runtime.implementation` becomes `shen-scheme`.
   - `runtime.sha256` becomes the identity digest. It is per platform and per build, as the shen-go hash already is.
   - The new `runtime.binary_sha256` and `runtime.support` record the parts.
   - The stale `compiler` block entries are `shen.py`, `modelcheck.py` and `spec/__init__.py` (`souffle/compile.py` is already stale on `main`). No gate reads the block today.
   - The artifacts and bundle digests must not move. G5 and the spec compiler tests show the runtime does not change them, and the repin commit should say so with a diff.
   - `src/capcov/shen_runtime.py` sits outside `claims/` and is therefore not in the compiler block. Either move it or extend the block.
5. **Docs.**
   - Re-measure `docs/typed-claim-authority.md` "Measured constraints (shen-go c12933d)", including the 60 s bifrost note.
   - The `docs/production-roadmap.md` §2 Runtime row needs a new full gate run at the switching revision: a new `docs/validation/<rev>.md` with all four families and `nix flake check`.
   - `docs/system-specifications.md` names the pinned shen-go binaries.
   - `docs/ir-specification.md` does not name a runtime.
6. **Modelcheck facts.** `checker_binary` changes, so every `model_well_formed` fact must be re-minted under the new runtime.

## Recommendation

* **shen-scheme**
  - Switch to it once steps 1 and 2 land.
  - At `fef4b09` it passes the whole `shen` family, including G5, the typed authority differential and the text contract.
  - It runs the typed differential about 21× faster than shen-go (17.4 s against 364.4 s) and the family in under a quarter of the time.
  - What blocks the default now:
    - the fork PR being merged and repinned;
    - the CI build cost or a cache;
    - aarch64-linux;
    - reproducibility for the manifest digest;
    - the deliberate manifest and doc repin.
* **shen-c** (`05a84f1`)
  - It is correct on everything measured, builds on every platform tried, and is the simplest to package.
  - It is only modestly faster than shen-go on the typed authority (273.0 s against 364.4 s) and slower on its untyped batch.
  - It is the fallback.
* **shen-go** stays the default in this branch.
