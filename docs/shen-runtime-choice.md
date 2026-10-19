# Choosing the Shen runtime: shen-go, shen-scheme or shen-c

Status: **proposal; shen-go stays the default.** This branch makes the runtime
selectable and measures the alternatives. It does not change the default, the
v2 pack manifests or any recorded evidence.

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
    - the modelcheck certificate, whose `recheck` accepts the exact key set of
      the recorded runtime;
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
  - They are not in the `shen` family or in `checks`, so CI is unchanged.
  - The pins are below.

## Pins

| Runtime | Source | Build inputs (fixed-output) | Store path (aarch64-darwin) |
|---|---|---|---|
| shen-go (default, unchanged) | pyrex41/shen-go `c12933d` | — | `/nix/store/xc7f80vh6gb5j6ar0452sflfs8jm1xxm-shen-go-0-unstable-2026-09-14` |
| shen-scheme | pyrex41/shen-scheme `d037ae6aed9da67245e8a19683bbfde49a971078`, `sha256-WoXtvQoXf1kzgcX/eJL3R/4o5IQzQ8DJMrswq9GFwiE=` | ShenOSKernel-42.2 `sha256-HQInMANlTTTsAgrmfLIU7OxBDe4zUEGf+AfYK2UmeNg=`; Chez 10.3.0 `sha256-0jfZh0xuiwzPd1jaqChqboJVKLE847K8pW6x9zzdvCw=`; prebuilt shen-scheme v0.26 (precompiles the kernel) macOS `sha256-qcMhooba81TdqKtR6ysZHL3DOcIIfkSQSIyIzkYvXcY=`, linux `sha256-KFk4TzsWzWz1lghM//fi2dWzGhHfPR98nh8XRu1u95g=` | `/nix/store/k5wnkyb0p0l1mzsb7iy2r61jwn3qj0al-shen-scheme-0-unstable-2026-10-11` |
| shen-c | pyrex41/shen-c `05a84f1d5296fdd0bb5202cfe875c986f9836607`, `sha256-h2//wgpBfZXo6H9I7eOMYjfZs5e1mp/VdByf5D9JgTQ=` | — | `/nix/store/lb0dxscsxzj3bn1ak1248qib1hyscg5l-shen-c-0.3.0-unstable-2026-10-19` |

**shen-scheme build**
- The recipe is upstream's own: `fetch-kernel fetch-prebuilt precompile-with-prebuilt all`.
  The three downloads are replaced by fetches carrying the Makefile's checksums,
  and Chez 10.3.0 is built from source (nixpkgs' chez is 10.4.1).
- The nix build's `compiled/*.scm` and `shen-scheme.scm` are byte-identical to
  the benchmarked build. `share/shen-scheme/compiled.sha256` records them, and
  the executable is identical too (`b94c9d65…`).
- The boot files and `runtime.so` differ from the benchmarked host build.
- Precompiling with the pinned shen-go instead of the prebuilt also works, but
  the result is not byte-identical: gensym numbering differs, and so does symbol
  escaping (`kl:r#` against `|kl:r#|`). It would not be the measured binary.
- `dontStrip` is required: `strip` rewrites the boot files, which then fail
  Chez's version check.

**shen-c build**
- `make` with clang and no pkg-config, as in shen-c's own flake. Its test suite
  is not run here.
- The installed `shen-c` runs with an empty environment (kernel and standard
  library built in).

**Not reproducible**
- `nix build --rebuild` reports that both the shen-scheme and the shen-c
  outputs differ between two builds of the same derivation on this host.
- A recorded runtime digest is therefore stable only for one build, or through
  a binary cache, not across rebuilds.
- Whether the pinned shen-go build is reproducible was not checked.

**Not verified**
- Linux builds: no Linux host here. The shen-scheme Linux path patches the
  prebuilt with `autoPatchelf` and links `libuuid`.

Runtime file digests (aarch64-darwin, this build):

| File | sha256 |
|---|---|
| shen-go `bin/shen` | `6660a921980e471f6c3cca5b2ebe911c55212678a31a6dde63d7c1a9b3f148c9` |
| shen-scheme `bin/shen-scheme` | `b94c9d6578b0d9fd133836b1e09a15b8c73f9634270c3039159e846c06d55100` |
| shen-scheme `lib/shen-scheme/petite.boot` | `3786eeb7fdf31705d582f2544d5380acc440a71692a4135a6128d2f4d930a854` |
| shen-scheme `lib/shen-scheme/scheme.boot` | `5c7691f3450dd928f078bd3befda922589715a1230493ce8f991d38eadc8e5e6` |
| shen-scheme `lib/shen-scheme/shen-scheme/runtime.so` | `122628db5d7551ad897d3d2b010ed74ea3a970098a70d7b1699fc2387dfbd875` |
| shen-scheme identity digest | `88cb65d3291915b7acf99b2157b8dce14cf6934cb5624f03ecf6e6f129caf021` |
| shen-c `bin/shen-c` | `ca4dce70828afb2d27e4b44ba6397fb64b5f593e5d89634378a30d5a136267ee` |

## Measured: the `shen` family under each runtime

Revision `a541e7d` (this branch, before this document), 2026-10-19, one shard (`--shard 1/1`),
`CAPCOV_SHEN_REQUIRED=1`. The machine is the macOS 27 / Apple M5 host of the
[e5bf644 report](validation/e5bf644.md). It was shared with other sessions,
with load average 17 to 36, so wall times are upper bounds. Runtimes ran one
after another:

```sh
nix develop --no-update-lock-file 'path:.#shen-runtimes' --command bash -lc \
  "export CAPCOV_SHEN_REQUIRED=1 CAPCOV_SHEN_IMPL=<impl>; \
   PYTHONPATH=src uv run --frozen --extra probe-python --extra treesitter --extra faults-property \
   --group packaging python scripts/check-skips.py --family shen --shard 1/1 --result shard-shen-1-1.json"
```

| Runtime | Ran | Failed | Skipped | Expected failures | Shard s | Typed differential s (typed batch / untyped batch) | G5 byte-identity |
|---|---|---|---|---|---|---|---|
| shen-go | 152 | 0 | 1 | 4 | 327.8 | 324.1 (312.3 / 11.7) | pass (94.9 s; bridge 28.7 s) |
| shen-scheme | 152 | **3** | 1 | 4 | 109.9 | 19.5 (14.6 / 4.2) | pass (46.9 s; bridge 14.8 s) |
| shen-c | 152 | 0 | 1 | 4 | 292.0 | 289.8 (242.1 / 47.3) | pass (53.3 s; bridge 17.5 s) |

* The skip is the accepted one (`LiveModelTest` needs `CAPCOV_MODEL_DIR`).
* The 152 tests are the 148 of the e5bf644 report plus the four live tests this
  branch adds.
* An earlier run at `2509b75` (before `TextContractTest`) measured shen-go 431.5 s
  (typed batch 406.4 s) and shen-scheme 198.5 s (typed batch 20.8 s), with only
  the operations failure below.
* Typed authority results were identical on all three runtimes: 3148 units, the
  same disagreement set and the same verdicts.

Result sha256:
- shen-go `7c1d8e8a2ee1e006fb0eb24ffe051889e4e92b5f83789f1f37f6dc660f2611f7`
- shen-scheme `fb9d148a3b06638217f36edb0c9bde2c211fd4f28d4582c89d59e01227c08333`
- shen-c `fd7b6c7078d6de3b89ba4201e84b1e465161b03df9afb052b9905d5575cef1ec`

The standalone benchmark of the same typed-authority workload agrees in shape:
shen-go `c12933d` took a median of 231 s and shen-scheme 7.0 s.

### Divergences, classified

All three shen-scheme failures have one cause.

| Test | Runtime | Class | Cause |
|---|---|---|---|
| `test_operations.NativeOperationTests.test_transport_unicode_quotes_and_determinism` | shen-scheme | runtime defect (string encoding) | The key `issue-"\⏎λ雪` comes back as `issue-"\⏎Î»é›ª`. |
| `test_shen_runtime_choice.TextContractTest` (`λ雪`, `naïve café`) | shen-scheme | runtime defect (same) | A **positive certificate whose strings are double-encoded** is returned, so it differs from Python's certificate. It is not refused. |

**Cause**
- The kernel's reader builds strings byte by byte (`n->string` of each UTF-8
  byte), so `"λ"` is two characters, U+00CE and U+00BB. shen-go and shen-c work
  the same way.
- shen-scheme's `pr` override (`src/overrides.shen`) then writes binary ports
  with `string->utf8`, which encodes each of those characters again. The result
  is mojibake for every byte above 127.
- shen-go and shen-c write the bytes back unchanged.
- ASCII text is unaffected, which is why everything else, G5 included, agrees.

**Fix**
- Make `pr` write one byte per character for binary sinks (a Latin-1
  transcoder, or `put-u8` per char) in pyrex41/shen-scheme. Pin the new
  revision and re-run.
- A capcov-side workaround (rebinding `*stoutput*` to a Latin-1 port) is not
  reachable: `scm.` interop is undefined in script mode at this revision, and
  `pr` is protected.

No shen-c divergence was found at `05a84f1`. The benchmark's earlier DIFFERS on
c-untyped, d-g5 and e-draft were at `802e724`, before the fixes merged.

Tests that hardcoded shen-go now follow the selected runtime:
- `test_shen_transport`;
- `test_modelcheck` (the certificate keys, the preflight);
- `test_typed_authority.ForgedTypedIRTest`;
- `test_ir_specification.DraftTypecheckTest`.

`FakeLauncherFailureTest` tests the transport, not a runtime. It pins
`CAPCOV_SHEN_IMPL=shen-go` around its fake binary, because a fake has no
shen-scheme support files.

## What switching the default would take

1. **Fix shen-scheme's string output** (above) and pin the fixed revision.
   `TextContractTest` and the operations unicode test must pass. Until then
   shen-scheme gives wrong answers on non-ASCII text, which is disqualifying for
   an authority.
2. **Make it hermetic on Linux CI.**
   - Add shen-scheme to the `shen` family (`packages`, `BIFROST_SHEN_SCHEME`)
     and to `checks` (an evaluator smoke like `shen-evaluator-smoke`).
   - Build it on x86_64-linux and aarch64-linux; the prebuilt there needs
     `autoPatchelf`. Not verified on this host.
   - Building Chez costs about 7 minutes per platform without a binary cache.
   - The build is not bit-reproducible (above). Before a manifest records its
     digest, either make it reproducible or serve it from a pinned binary cache.
3. **Flip `shen_runtime.DEFAULT_IMPL`.** Every record then names shen-scheme.
   - Records that used to say `shen_go`/`shen_go_sha256` now say
     `binary`/`binary_sha256` plus `support_sha256`.
   - Decide whether to keep the shen-go key shape as a legacy reader in
     `modelcheck.recheck` (already accepted) and the operations evidence.
4. **Repin the v2 pack manifests in one deliberate commit**
   (`src/capcov/claims/{static,replay,observation}/rules-*-v2.manifest.json`):
   - `runtime.implementation` becomes `shen-scheme`.
   - `runtime.sha256` becomes the identity digest. That is per platform and per
     build, as the shen-go hash already is ("the Linux-Nix runtime hash").
   - The new `runtime.binary_sha256` and `runtime.support` record the parts.
   - The `compiler` block entries this branch already makes stale:
     `shen.py`, `modelcheck.py`, `spec/__init__.py`. `souffle/compile.py` is
     already stale on `main`.
   - The artifacts and bundle digests must not move. G5 and the spec compiler
     tests show the runtime does not change them, and the repin commit should
     say so with a diff.
   - Today no gate reads the compiler block, so the stale entries do not fail
     a test.
   - `src/capcov/shen_runtime.py` sits outside `claims/` and is therefore not in
     the compiler block. Either move it under `claims/` or extend the block,
     since it decides what runs.
5. **Docs.**
   - `docs/typed-claim-authority.md` "Measured constraints (shen-go c12933d)" needs
     re-measuring, including the 60 s bifrost note.
   - The `docs/production-roadmap.md` §2 Runtime row ("Bifrost/Shen-Go process
     per request") and the rows that cite the e5bf644 gate need a new full gate
     run at the switching revision: a new `docs/validation/<rev>.md` with all
     four families and `nix flake check`.
   - `docs/system-specifications.md` names the pinned shen-go binaries.
   - `docs/ir-specification.md` does not name a runtime.
6. **Modelcheck facts.** `checker_binary` changes, so every
   `model_well_formed` fact must be re-minted under the new runtime.

## Recommendation

* **shen-scheme**
  - It is the runtime to move to: the typed authority differential runs about
    17× faster (19.5 s against 324.1 s), and the whole family in a third of the
    time.
  - It agrees with shen-go on every ASCII workload, including G5 and the typed
    authority.
  - It is **blocked** by one runtime defect: non-ASCII output is double-encoded,
    and that yields wrong certificates, not refusals.
  - Fix that in the shen-scheme fork, re-pin, rerun this table, verify the Linux
    build, then switch with the manifest repin in step 4.
* **shen-c** (`05a84f1`)
  - It is correct on everything measured here, text included, and is the
    simplest to package (one self-contained binary, no bootstrap).
  - It is only modestly faster than shen-go on the typed authority (289.8 s
    against 324.1 s) and slower on its untyped batch (47.3 s against 11.7 s).
  - It is a sound fallback, not the performance win.
* **shen-go** stays the default until step 1 lands.
