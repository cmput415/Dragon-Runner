import os
from io         import StringIO
from cli        import parse_cli_args
from difflib    import unified_diff
from config     import load_config, gather_tests, Executable, Config
from runner     import run_toolchain, ToolchainResult
from log        import log
from test       import Test
from typing     import List
from colorama   import init, Fore

# initialize terminal colors
init(autoreset=True)

def source_executable_env(exe: Executable):
    """
    Source all environment variables defined in the env
    map of the current executable.
    """
    for key, value in exe.env.items():
        os.environ[key] = value

def result_diff(produced_out: str, expected_out: StringIO):
    
    # TODO: convert this function to work with StringIO
    expected_bytes = expected_out.getvalue(),
    diff = list(unified_diff(
        str(expected_bytes).splitlines(keepends=True),
        str(produced_out).splitlines(keepends=True),
        fromfile='expected',
        tofile='produced',
        n=3
    ))
    return str(diff)

def error_diff(produced_err: str, expected_out: str):
    # TODO: implement the proper Error substring leniency 
    return expected_out not in produced_err

def print_diff(diff):
    if diff:
        print("Diff between expected and produced output:")
        for line in diff:
            if line.startswith('+'):
                print(Fore.GREEN + line, end='')
            elif line.startswith('-'):
                print(Fore.RED + line, end='')
            else:
                print(line, end='')
    else:
        print("No differences found.")
    print("")


def log_result(test: Test, did_pass: bool):
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
    tests: List[Test] = gather_tests(config.test_dir)
    
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
                    #diff = result_diff(result.stdout, test.expected_out)
                    #error_diff(result.stderr, test.expected_out)
                    error_diff = diff = False 
                    if not diff or not error_diff:
                        log_result(test, True)
                        pass_count += 1
                    else:
                        log_result(test, False)
            
            print("PASSED: ", pass_count, "/", len(tests))

if __name__ == "__main__":
    main()

