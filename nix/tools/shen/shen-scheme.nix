# Latest upstream tizoc/shen-scheme at the time of qualification, not a moving ref.
# Build the current Scheme sources with the verified upstream v0.52 compiler.
{ lib, stdenv, fetchurl, libuuid, autoPatchelfHook }:
let
  revision = "8d261518db17fbfec32d1b268b40ed216b925c74";
  chezVersion = "10.3.0";
  binaryBootstrap = stdenv.hostPlatform.system != "aarch64-linux";
  darwin = stdenv.hostPlatform.isDarwin;
  chezSha256 = "d237d9874c6e8b0ccf7758daa8286a6e825528b13ce3b2bca56eb1f73cddbc2c";
  chez = fetchurl {
    url = "https://github.com/cisco/ChezScheme/releases/download/v${chezVersion}/csv${chezVersion}.tar.gz";
    sha256 = chezSha256;
  };
  bootstrap = stdenv.mkDerivation {
    pname = "shen-scheme-bootstrap";
    version = "0.52";
    src = fetchurl {
      url = "https://github.com/tizoc/shen-scheme/releases/download/v0.52/shen-scheme-v0.52-" +
        (if !binaryBootstrap then "src" else if darwin then "macOS-arm64-bin" else "linux-x64-bin") + ".tar.gz";
      sha256 = if !binaryBootstrap then "6f3d4bdfa86a15e7916288f320e6a2f8d1739bdc5a93bf70d383b9ee83c86974"
        else if darwin then "44e980d192d156859d06374e554813e1dc1e81210b95e9b1e23eb5e85276106b"
        else "aa711f576ea0ec96d86b0120eeba875153317a9af9e6a69f9c6ef4c00a4ad8c9";
    };
    nativeBuildInputs = lib.optionals (binaryBootstrap && !darwin) [ autoPatchelfHook ];
    buildInputs = lib.optionals (!darwin) [ libuuid stdenv.cc.cc.lib ];
    dontConfigure = true;
    dontStrip = true;
    enableParallelBuilding = false;
    buildPhase = if binaryBootstrap then "true" else ''
      mkdir -p _build/chez
      tar xzf ${chez} -C _build/chez
      touch _build/chez/.csv${chezVersion}-${chezSha256}.extracted
      make all git_tag=v0.52
    '';
    installPhase = if binaryBootstrap then ''
      mkdir -p "$out"
      cp -r bin lib "$out/"
    '' else ''
      make install prefix="$out" git_tag=v0.52
    '';
  };
  kernel = fetchurl {
    # Unmodified upstream kernel commit, packaged independently of the host.
    url = "https://github.com/pyrex41/shen-sources/releases/download/upstream-ec16a9f/ShenOSKernel-43.1-ec16a9f.tar.gz";
    sha256 = "060066a8f84d9a2f7d41cb3b37b986a8d4653279752b739b5063cd648d9baacd";
  };
in stdenv.mkDerivation {
  pname = "shen-scheme";
  version = "0.52-unstable-8d26151";
  src = fetchurl {
    url = "https://codeload.github.com/tizoc/shen-scheme/tar.gz/${revision}";
    sha256 = "adf1a2274638e2c8cc5b14cea511e6da6b28383d935911cba322b03e9fffeefd";
  };
  dontConfigure = true;
  dontStrip = true;
  buildPhase = ''
    runHook preBuild
    sh ${../../../scripts/build-upstream-shen.sh} ${bootstrap} ${kernel} "$PWD/result"
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r result/bin result/lib "$out/"
    runHook postInstall
  '';
  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    unset SHEN_SCHEME_HOME SHEN_SCHEME_RUNTIME
    test "$("$out/bin/shen-scheme" eval -e '(+ 20 22)')" = 42
    test "$("$out/bin/shen-scheme" eval -e '(eval-kl [scm. "(procedure-arity-mask kl:shen.search-user-datatypes-h)"])')" = 128
    runHook postInstallCheck
  '';
  passthru = {
    inherit revision chezVersion;
    upstreamRevision = revision;
    shenVersion = "43.1";
    kernelRevision = "ec16a9fa4fc2e87e2aa336fb1ae30e8ac2266394";
  };
  meta = {
    description = "Upstream Chez Scheme port of Shen";
    homepage = "https://github.com/tizoc/shen-scheme";
    license = lib.licenses.bsd3;
    mainProgram = "shen-scheme";
    platforms = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
  };
}
