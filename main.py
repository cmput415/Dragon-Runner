from typing import List, Dict, Tuple
from cli import parse_cli_args
import os

from config import load_config, gather_tests, Config
from runner import run_toolchain

def main():

    args = parse_cli_args()
    config = load_config(args.config_file)
    tests = gather_tests(config.test_dir)
        
    for triple in tests:
        print(triple)
    
    for exe in config.executables:
        print("-- Running executable:\t", exe.id)
        for toolchain in config.toolchains:
            print("-- Running Toolchain:\t", toolchain.name) 
            for test in tests:
                run_toolchain(test, toolchain, exe)
    #toolchain = config.toolchains['gazprea-llc']

    #for test in tests:
    #    print(f"Running test: {test}")
    #    run_toolchain(toolchain, triple, config.to_dict())

if __name__ == "__main__":
    main()

