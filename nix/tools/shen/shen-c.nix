# shen-c, the C port of Shen (reference-counted compiler and runtime), at a
# fixed commit. Only the command-line binary is installed: the kernel and
# standard library are compiled into it, so it needs no SHEN_C_HOME. This
# follows the build of shen-c's own flake (make with clang, no pkg-config);
# its test suite is not run here.
{
  lib,
  stdenv,
  fetchFromGitHub,
  clang,
  python3,
}:

let
  revision = "05a84f1d5296fdd0bb5202cfe875c986f9836607";
in
stdenv.mkDerivation {
  pname = "shen-c";
  version = "0.3.0-unstable-2026-10-19";
  src = fetchFromGitHub {
    owner = "pyrex41";
    repo = "shen-c";
    rev = revision;
    hash = "sha256-h2//wgpBfZXo6H9I7eOMYjfZs5e1mp/VdByf5D9JgTQ=";
  };

  nativeBuildInputs = [ clang python3 ];

  dontConfigure = true;
  enableParallelBuilding = true;

  # The build must not find a host libgc through pkg-config.
  env.PKG_CONFIG = "/nonexistent/shen-rc-pkg-config";

  buildPhase = ''
    runHook preBuild
    make -j$NIX_BUILD_CORES CC=clang
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm0755 bin/shen-rc "$out/bin/shen-c"
    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    unset SHEN_C_HOME SHEN_RC_HOME
    "$out/bin/shen-c" --version
    test "$("$out/bin/shen-c" eval -e '(+ 20 22)')" = 42
    runHook postInstallCheck
  '';

  passthru = { inherit revision; };

  meta = {
    description = "C port of the Shen language";
    homepage = "https://github.com/pyrex41/shen-c";
    license = with lib.licenses; [ bsd3 mit ];
    mainProgram = "shen-c";
    platforms = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
  };
}
