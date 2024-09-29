import os
from colorama               import init, Fore
from dragon_runner.cli      import parse_cli_args
from dragon_runner.config   import load_config, Config
from dragon_runner.runner   import ToolChainResult, TestResult, ToolChain
from dragon_runner.runner   import run_toolchain, get_test_result
from dragon_runner.log      import log, log_multiline
from dragon_runner.testfile import TestFile
from dragon_runner.grader   import grade
from dragon_runner.utils    import bytes_to_str

# initialize terminal colors
init(autoreset=True)

def log_result(test: TestFile, result: TestResult): 
    if result.did_pass:
        if result.error_test:
            log(Fore.GREEN + "[ERROR PASS] " + Fore.RESET + test.file)
        else:
            log(Fore.GREEN + "[PASS] " + Fore.RESET + test.file)
    else:
        if result.error_test:
            log(Fore.RED + "[FAIL] " + Fore.RESET + test.file)
        else:
            log(Fore.RED + "[ERROR FAIL] " + Fore.RESET + test.file)

def log_toolchain_result(test: TestFile, result: ToolChainResult, tc: ToolChain):
    """
    log relevant info when the toolchain panics at some intermediate step
    """
    if result.success:
        return
    log(Fore.RED + "[TOOLCHAIN ERROR] " + Fore.RESET + test.file)
    log("Failed on step: ", result.last_step.name, indent=2)
    log("Exited with status: ", result.exit_code, indent=2)
    log("With command: ", ' '.join(result.last_command), indent=2)
    log(f"With stderr: ({len(result.stderr.getbuffer())} bytes)", indent=2)
    log_multiline(bytes_to_str(result.stderr), indent=4)
    log(f"With stdout: ({len(result.stdout.getbuffer())} bytes)", indent=2)
    log_multiline(bytes_to_str(result.stdout), indent=4)
 
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
        return grade()
    
    # run the toolchain
    for exe in config.executables:
        log("Running executable:\t", exe.id)
        exe.source_env()
        for toolchain in config.toolchains:
            log("Running Toolchain:\t", toolchain.name)
            pass_count = 0
            test_count = 0
            for spkg in config.sub_packages:
                log(f"Entering subpackage {spkg.rel_dir_path}")
                sp_pass_count = 0
                sp_test_count = len(spkg.tests)
                for test in spkg.tests:
                    tc_result: ToolChainResult = run_toolchain(test, toolchain, exe)
                    if not tc_result.success:
                        log_toolchain_result(test, tc_result, toolchain)
                    else:
                        test_result: TestResult = get_test_result(tc_result, test.expected_out)
                        if test_result.did_pass:
                            log_result(test, test_result)
                            sp_pass_count += 1
                        else:
                            log(test_result.diff)
                            log_result(test, test_result)
                pass_count += sp_pass_count
                test_count += sp_test_count
                log("Passed: ", sp_pass_count, "/", sp_test_count)
            log("PASSED: ", pass_count, "/", test_count)
    
    if pass_count == test_count:
        return 0
    return 1

if __name__ == "__main__":
    main()
