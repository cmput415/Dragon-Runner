import os
from cli import parse_cli_args
from difflib import unified_diff
from config import load_config, gather_tests, Executable, Config
from runner import run_toolchain, ToolchainResult
from log import log
from test import Test
from typing import List

def source_executable_env(exe: Executable):
    """
    Source all environment variables defined in the env
    map of the current executable.
    """
    for key, value in exe.env.items():
        os.environ[key] = value

def result_diff(produced_out: str, expected_out: str):
    
    diff = list(unified_diff(
        expected_out.splitlines(keepends=True),
        produced_out.splitlines(keepends=True),
        fromfile='expected',
        tofile='produced',
        n=3
    ))
    return diff

def error_diff(produced_err: str, expected_out: str):
    # TODO: implement the proper Error substring leniency 
    return expected_out not in produced_err

def print_diff(diff):
    if diff:
        print("Diff between expected and produced output:")
        print(''.join(diff))
    else:
        print("No differences found.")

def main():
    args = parse_cli_args()
    config: Config      = load_config(args.config_file)
    tests : List[Test]  = gather_tests(config.test_dir)
     
    for triple in tests:
        log(triple, level=0)
    
    for exe in config.executables:
        log("-- Running executable:\t", exe.id)
        source_executable_env(exe)
        for toolchain in config.toolchains:
            log("-- Running Toolchain:\t", toolchain.name) 
            
            pass_count = 0
            for test in tests:
                result: ToolchainResult = run_toolchain(test, toolchain, exe)
                if not result.success:
                    log("Toolchain Failed: ", result)
                else: 
                    diff = result_diff(result.stdout, test.expected_out)
                    if not diff:
                        log("[PASS]") 
                        pass_count += 1
                    elif not error_diff(result.stderr, test.expected_out):
                        log("[PASS]")
                        pass_count += 1
                    else:
                        log("[FAIL]")
                        print_diff(diff)
            
            print("PASSED: ", pass_count, "/", len(tests))

if __name__ == "__main__":
    main()

