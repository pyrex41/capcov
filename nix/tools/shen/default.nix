# The Shen runtimes the claim-semantics tests drive, and their launcher.
# shen-scheme is the default (CAPCOV_SHEN_IMPL unset); shen-go stays in the
# family as the cross-check runtime (docs/shen-runtime-choice.md).
{ pkgs }:

rec {
  shenScheme = pkgs.callPackage ./shen-scheme.nix { };
  shenGo = pkgs.callPackage ./shen-go.nix { };
  bifrost = pkgs.callPackage ./bifrost.nix { };
  packages = [ shenScheme shenGo bifrost ];
  env = {
    # bifrost starts the binary these name; the Shen tests require them.
    BIFROST_SHEN_SCHEME = "${shenScheme}/bin/shen-scheme";
    BIFROST_SHEN_GO = "${shenGo}/bin/shen";
  };

  # A third runtime, selectable with CAPCOV_SHEN_IMPL=shen-c. Not part of the
  # family: only the `shen-runtimes` dev shell carries it.
  shenC = pkgs.callPackage ./shen-c.nix { };
  candidates = {
    packages = [ shenC ];
    env = {
      BIFROST_SHEN_C = "${shenC}/bin/shen-c";
    };
  };
}
