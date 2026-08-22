{
  description = "Dragon Runner";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            rustc
            cargo
            rustfmt
            clippy
          ];
          shellHook = ''
            echo "Dragon Runner development environment"
          '';
        };

        packages.default = pkgs.rustPlatform.buildRustPackage {
          pname = "dragon-runner";
          version = "0.1.0";
          src = ./.;
          cargoLock.lockFile = ./Cargo.lock;
          doCheck = false;
          meta = with pkgs.lib; {
            description = "The 415 compiler unit tester";
            license = licenses.mit;
            maintainers = [ ];
          };
        };
      });
}
