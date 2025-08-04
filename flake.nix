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
        
        python-packages = ps: with ps; [
          colorama
          pytest
          numpy
          flask
          flask-cors
        ];
        
        python-with-packages = pkgs.python3.withPackages python-packages;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python-with-packages
            python3Packages.pip
            python3Packages.setuptools
            python3Packages.wheel
          ];
          
          shellHook = ''
            echo "Dragon Runner development environment"
            export PYTHONPATH="$PWD:$PYTHONPATH"
          '';
        };

        packages.default = pkgs.python3Packages.buildPythonPackage {
          pname = "dragon-runner";
          version = "1.0.0";
          src = ./.;
          
          propagatedBuildInputs = python-packages pkgs.python3Packages;
          
          meta = with pkgs.lib; {
            description = "An experimental successor to the 415 tester";
            license = licenses.unfree;
            maintainers = [ ];
          };
        };
      });
}

