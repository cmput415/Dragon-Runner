import os
from typing import List, Dict
from cli import parse_cli_args
from config import load_config, gather_tests, Executable
from runner import run_toolchain

def source_executable_env(exe: Executable):
    """
    Source all environment variables defined in the env
    map of the current executable.
    """
    for key, value in exe.env.items():
        os.environ[key] = value

def main():

    args = parse_cli_args()
    config = load_config(args.config_file)
    tests = gather_tests(config.test_dir)
        
    for triple in tests:
        print(triple)
    
    for exe in config.executables:
        print("-- Running executable:\t", exe.id)
        source_executable_env(exe)

        for toolchain in config.toolchains:
            print("-- Running Toolchain:\t", toolchain.name) 
            for test in tests:
                run_toolchain(test, toolchain, exe)

if __name__ == "__main__":
    main()

