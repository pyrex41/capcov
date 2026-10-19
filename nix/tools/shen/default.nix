# The Shen runtime the claim-semantics tests drive: shen-go and its launcher.
{ pkgs }:

rec {
  shenGo = pkgs.callPackage ./shen-go.nix { };
  bifrost = pkgs.callPackage ./bifrost.nix { };
  packages = [ shenGo bifrost ];
  env = {
    # bifrost starts the binary this names; the Shen tests require both.
    BIFROST_SHEN_GO = "${shenGo}/bin/shen";
  };

  # Candidate runtimes, selected with CAPCOV_SHEN_IMPL (docs/shen-runtime-choice.md).
  # Not part of the family: only the `shen-runtimes` dev shell carries them.
  shenScheme = pkgs.callPackage ./shen-scheme.nix { };
  shenC = pkgs.callPackage ./shen-c.nix { };
  # shen-scheme builds only where its bootstrap binary runs (shen-scheme.nix).
  schemeAvailable = pkgs.lib.meta.availableOn pkgs.stdenv.hostPlatform shenScheme;
  candidates = {
    packages = pkgs.lib.optional schemeAvailable shenScheme ++ [ shenC ];
    env = pkgs.lib.optionalAttrs schemeAvailable {
      BIFROST_SHEN_SCHEME = "${shenScheme}/bin/shen-scheme";
    } // {
      BIFROST_SHEN_C = "${shenC}/bin/shen-c";
    };
  };
}
