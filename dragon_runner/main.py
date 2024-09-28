import os

from colorama               import init, Fore
from typing                 import List
from dragon_runner.cli      import parse_cli_args
from dragon_runner.config   import load_config, gather_tests, Executable, Config
from dragon_runner.runner   import run_toolchain, ToolchainResult
from dragon_runner.log      import log
from dragon_runner.testfile import TestFile
from dragon_runner.utils    import precise_diff, lenient_diff, get_test_result_string

# initialize terminal colors
init(autoreset=True)

def source_executable_env(exe: Executable):
    """
    Source all environment variables defined in the env
    map of the current executable.
    """
    for key, value in exe.env.items():
        os.environ[key] = value

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
    config: Config = load_config(args.config_file)
    if config.errors:
        log(config.errors)
        exit(1)
    
    # gather the tests
    tests: List[TestFile] = gather_tests(config.test_dir)
    
    # log the tests
    for triple in tests:
        log(triple, level=0) 

    # run the tester in grade mode
    if args.grade_file is not None:
        return grade_mode()
    
    # run the toolchain
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
                    diff = precise_diff(result.stdout, test.expected_out)
                    if not diff:
                        log_result(test, True)
                        pass_count += 1
                    else:
                        log(diff)
                        log_result(test, False)
             
            print("PASSED: ", pass_count, "/", len(tests))
    
    if pass_count == len(tests):
        exit(0)
    else:
        exit(1)

if __name__ == "__main__":
    main()

