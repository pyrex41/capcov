# shen-scheme, the Chez Scheme port of Shen, at a fixed commit, on the
# ShenOSKernel 43.1 sources and the Chez Scheme 10.3.0 release (not nixpkgs'
# chez, which is another version). The commit is pyrex41/shen-scheme#11, which
# writes the kernel's byte strings as bytes, on top of the fork's 43.1 upgrade.
#
# The upstream Makefile downloads Chez, the kernel and a prebuilt shen-scheme
# v0.26 (which precompiles the kernel to Scheme), none of which a sandboxed
# build may do. Here all three are fixed-output fetches with the Makefile's
# own checksums and the recipe is upstream's `fetch-kernel fetch-prebuilt
# precompile-with-prebuilt all`. Precompiling with the pinned shen-go instead
# also produces the sources, but not byte-identical ones (gensym numbering and
# symbol escaping differ), so it would not be the build the fork's own recipe
# makes and tests. The precompiled sources' digests are installed in
# share/shen-scheme/compiled.sha256 for comparison.
#
# The binary finds its boot files and runtime object at ../lib/shen-scheme
# relative to itself; nothing wraps it.
#
# No aarch64-linux: the only prebuilt for Linux is x86_64, and the pinned
# shen-go cannot stand in (its precompiled sources are not valid Chez input:
# "invalid sharp-sign prefix #-"). A source release with the precompiled
# sources would remove the bootstrap binary on every platform.
{
  lib,
  stdenv,
  fetchFromGitHub,
  fetchurl,
  libuuid,
  autoPatchelfHook,
}:

let
  revision = "fef4b0906022b495586957a3132de5e84125b547";
  shenVersion = "43.1";
  chezVersion = "10.3.0";
  prebuiltVersion = "0.26";
  os = if stdenv.hostPlatform.isDarwin then "macOS" else "linux";
  # The Makefile's chez_sha256_10.3.0, in hex, names the extraction stamp.
  chezSha256 = "d237d9874c6e8b0ccf7758daa8286a6e825528b13ce3b2bca56eb1f73cddbc2c";
  chez = fetchurl {
    url = "https://github.com/cisco/ChezScheme/releases/download/v${chezVersion}/csv${chezVersion}.tar.gz";
    hash = "sha256-0jfZh0xuiwzPd1jaqChqboJVKLE847K8pW6x9zzdvCw=";
  };
  kernel = fetchurl {
    url = "https://github.com/Shen-Language/shen-sources/releases/download/shen-${shenVersion}/ShenOSKernel-${shenVersion}.tar.gz";
    hash = "sha256-kA7t70T0QK94+Tle0G5onOFgRUb8MJ9bx8i8hMxlGSA=";
  };
  prebuilt = fetchurl {
    url = "https://github.com/tizoc/shen-scheme/releases/download/v${prebuiltVersion}/shen-scheme-v${prebuiltVersion}-${os}-bin.tar.gz";
    hash = {
      macOS = "sha256-qcMhooba81TdqKtR6ysZHL3DOcIIfkSQSIyIzkYvXcY=";
      linux = "sha256-KFk4TzsWzWz1lghM//fi2dWzGhHfPR98nh8XRu1u95g=";
    }.${os};
  };
in
stdenv.mkDerivation {
  pname = "shen-scheme";
  version = "0-unstable-2026-10-19";
  src = fetchFromGitHub {
    owner = "pyrex41";
    repo = "shen-scheme";
    rev = revision;
    hash = "sha256-JVu7kg4g453VQ0RN7JxHVZPqgBR9Qi/uCYgQjAUqSyI=";
  };

  buildInputs = lib.optionals stdenv.hostPlatform.isLinux [ libuuid ];
  # Only the bootstrap binary needs patching; it is not installed.
  nativeBuildInputs = lib.optionals stdenv.hostPlatform.isLinux [ autoPatchelfHook ];
  dontAutoPatchelf = true;

  dontConfigure = true;

  postPatch = ''
    mkdir -p _build/chez
    tar xzf ${chez} -C _build/chez
    touch _build/chez/.csv${chezVersion}-${chezSha256}.extracted
    tar xzf ${kernel}
    cp ShenOSKernel-${shenVersion}/klambda/*.kl kl/
    tar xzf ${prebuilt} -C _build
  '' + lib.optionalString stdenv.hostPlatform.isLinux ''
    autoPatchelf _build/shen-scheme-v${prebuiltVersion}-${os}-bin
  '';

  # Chez's own build is not parallel-safe through the outer Makefile.
  enableParallelBuilding = false;

  buildPhase = ''
    runHook preBuild
    make precompile-with-prebuilt
    make all git_tag=${builtins.substring 0 7 revision}
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    make install prefix="$out" git_tag=${builtins.substring 0 7 revision}
    mkdir -p "$out/share/shen-scheme"
    sha256sum shen-scheme.scm compiled/*.scm > "$out/share/shen-scheme/compiled.sha256"
    runHook postInstall
  '';

  # strip rewrites the Chez boot files and runtime object under lib/, which
  # then fail their version check; the installed files are the built ones.
  dontStrip = true;

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    unset SHEN_SCHEME_HOME SHEN_SCHEME_RUNTIME
    "$out/bin/shen-scheme" --version
    test "$("$out/bin/shen-scheme" eval -e '(+ 20 22)')" = 42
    runHook postInstallCheck
  '';

  passthru = { inherit revision shenVersion chezVersion prebuiltVersion; };

  meta = {
    description = "Chez Scheme port of the Shen language";
    homepage = "https://github.com/pyrex41/shen-scheme";
    license = lib.licenses.bsd3;
    mainProgram = "shen-scheme";
    platforms = [ "aarch64-darwin" "x86_64-linux" ];
  };
}
