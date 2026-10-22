# shen-scheme, the Chez Scheme port of Shen: release v0.52-pyrex41.4 of the
# pyrex41/shen-scheme fork (tag on 4366e3d), which is upstream tizoc/shen-scheme
# 05cf325 (v0.52 plus upstream's byte-string fix #44) plus the fork commits in
# its FORK.md, on kernel ShenOSKernel 43.1.2: community 43.1 plus
# Shen-Language/shen-sources#117 (the type checker dereferences the checked term
# once, and not at all on an empty hypothesis or datatype list), released on
# pyrex41/shen-sources. That fix roughly halves the
# instructions of capcov's typed authority.
# It builds on Chez Scheme 10.3.0, the release its Makefile pins (not nixpkgs'
# chez, which is another version).
#
# The release's source tarball (`make source-release`, upstream's recipe) ships
# the kernel already compiled to Scheme (compiled/*.scm, shen-scheme.scm,
# shen-scheme-runtime.ss), so the build needs no bootstrap Shen: only the Chez
# source, a fixed-output fetch with the Makefile's own checksum, and `make all`.
# docs/shen-runtime-choice.md has the details.
#
# The binary finds its boot files and runtime object at ../lib/shen-scheme
# relative to itself; nothing wraps it.
{
  lib,
  stdenv,
  fetchurl,
  libuuid,
}:

let
  version = "0.52-pyrex41.4";
  revision = "4366e3d0affbfc592b298ab3199ca275c76cb974";
  chezVersion = "10.3.0";
  # The Makefile's chez_sha256_10.3.0, in hex, names the extraction stamp.
  chezSha256 = "d237d9874c6e8b0ccf7758daa8286a6e825528b13ce3b2bca56eb1f73cddbc2c";
  chez = fetchurl {
    url = "https://github.com/cisco/ChezScheme/releases/download/v${chezVersion}/csv${chezVersion}.tar.gz";
    hash = "sha256-0jfZh0xuiwzPd1jaqChqboJVKLE847K8pW6x9zzdvCw=";
  };
in
stdenv.mkDerivation {
  pname = "shen-scheme";
  inherit version;
  src = fetchurl {
    url = "https://github.com/pyrex41/shen-scheme/releases/download/v${version}/shen-scheme-v${version}-src.tar.gz";
    hash = "sha256-GF4UmvOe8eqw23Gg9loUqRG4wu88o3pkJxL4u8LcGq0=";
  };

  buildInputs = lib.optionals stdenv.hostPlatform.isLinux [ libuuid ];

  dontConfigure = true;

  postPatch = ''
    mkdir -p _build/chez
    tar xzf ${chez} -C _build/chez
    touch _build/chez/.csv${chezVersion}-${chezSha256}.extracted
  '';

  # Chez's own build is not parallel-safe through the outer Makefile.
  enableParallelBuilding = false;

  buildPhase = ''
    runHook preBuild
    make all git_tag=v${version}
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    make install prefix="$out" git_tag=v${version}
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
    # Byte strings: a UTF-8 literal prints as its own bytes.
    printf '\316\273\351\233\252 caf\303\251' > expected
    printf '(pr "%s" (stoutput))\n' "$(cat expected)" > text.shen
    "$out/bin/shen-scheme" script text.shen > actual
    cmp expected actual
    runHook postInstallCheck
  '';

  passthru = { inherit revision chezVersion; upstreamRevision = "05cf3257f177dc2d01ee12dd8432d6eccce624c9"; shenVersion = "43.1.2"; };

  meta = {
    description = "Chez Scheme port of the Shen language";
    homepage = "https://github.com/pyrex41/shen-scheme";
    license = lib.licenses.bsd3;
    mainProgram = "shen-scheme";
    platforms = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
  };
}
