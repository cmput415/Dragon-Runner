import os

from colorama               import init, Fore
from typing                 import List
from dragon_runner.cli      import parse_cli_args
from dragon_runner.config   import load_config, Config
from dragon_runner.runner   import run_toolchain, ToolChainResult
from dragon_runner.log      import log
from dragon_runner.testfile import TestFile
from dragon_runner.utils    import precise_diff

# initialize terminal colors
init(autoreset=True)

def log_result(test: TestFile, did_pass: bool):
    if did_pass:
        log(Fore.GREEN + "  [PASS] " + Fore.RESET + test.stem)
    else:
        log(Fore.RED + "  [FAIL] " + Fore.RESET + test.stem)

def grade_mode():
    # TODO
    pass

def main(): 
    # parse and verify the CLI arguments
    args = parse_cli_args()
    
    # parse and verify the config
    config = load_config(args.config_file)
    if not config:
        log(f"Could not open config file: {args.config_file}")
        return 1
    if config.error_collection:
        log(config.error_collection)
        return 1

    # display the config info before running tests
    config.log_test_info()

    # run the tester in grade mode
    if args.grade_file is not None:
        return grade_mode()
    
    # run the toolchain
    for exe in config.executables:
        log("Running executable:\t", exe.id)
        exe.source_env()
        for toolchain in config.toolchains:
            log("Running Toolchain:\t", toolchain.name)
            pass_count = 0
            for test in config.tests:
                result: ToolChainResult = run_toolchain(test, toolchain, exe)
                if not result.success:
                    log("Toolchain Failed: ", result)
                else:
                    #diff = get_test_diff(
                    #    result.stdout, result.stderr, test.expected_out
                    #) 
                    #diff = precise_match(result.stdout, result.stderr, test.expected_out)
                    diff = precise_diff(result.stdout, test.expected_out) 
                    if not diff:
                        log_result(test, True)
                        pass_count += 1
                    else:
                        log(diff)
                        log_result(test, False) 
            log("PASSED: ", pass_count, "/", len(config.tests))
    
    if pass_count == len(config.tests):
        exit(0)
    else:
        exit(1)

if __name__ == "__main__":
    main()

