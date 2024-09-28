import os
import difflib

from io                     import BytesIO
from colorama               import init, Fore
from typing                 import List
from dragon_runner.cli      import parse_cli_args
from dragon_runner.config   import load_config, gather_tests, Executable, Config
from dragon_runner.runner   import run_toolchain, ToolchainResult
from dragon_runner.log      import log
from dragon_runner.testfile import TestFile

# initialize terminal colors
init(autoreset=True)

def source_executable_env(exe: Executable):
    """
    Source all environment variables defined in the env
    map of the current executable.
    """
    for key, value in exe.env.items():
        os.environ[key] = value

def diff_byte_strings(bytes1: BytesIO, bytes2: BytesIO) -> str:
    
    content1 = bytes1.getvalue()
    content2 = bytes2.getvalue()
    
    # if the strings are exactly the same produce no diff
    if content1 == content2:
        return ""
    print("PRODUCED: " , content1)
    print("EXPECTED: " , content2)

    lines1 = content1.split(b'\n')
    lines2 = content2.split(b'\n')

    str_lines1 = [line.decode('utf-8') for line in lines1]
    str_lines2 = [line.decode('utf-8') for line in lines2]

    differ = difflib.Differ()
    diff = list(differ.compare(str_lines1, str_lines2))

    return '\n'.join(diff)

def error_diff(produced_err: BytesIO, expected_out: BytesIO):
    # TODO: implement the proper Error substring leniency 
    return diff_byte_strings

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
                    diff = diff_byte_strings(result.stdout, test.expected_out)
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

