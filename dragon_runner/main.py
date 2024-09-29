import os
from colorama               import init, Fore
from dragon_runner.cli      import parse_cli_args, CLIArgs
from dragon_runner.config   import load_config, Config
from dragon_runner.runner   import ToolChainResult, TestResult, ToolChain
from dragon_runner.runner   import run_toolchain, get_test_result
from dragon_runner.log      import log, log_multiline
from dragon_runner.testfile import TestFile
from dragon_runner.grader   import grade
from dragon_runner.utils    import bytes_to_str
from dragon_runner.harness  import TestHarness

# initialize terminal colors
init(autoreset=True)

def main(): 
    # parse and verify the CLI arguments
    args: CLIArgs = parse_cli_args()

    # parse and verify the config
    config = load_config(args.config_file)
    if not config:
        log(f"Could not open config file: {args.config_file}")
        return 1
    if config.error_collection:
        log(config.error_collection)
        return 1

    if args.verify:
        ccid = input("Enter your CCID: ")
        assert config and not config.error_collection
        found = False
        for sp in config.sub_packages:
            log("Searching.. ", sp.package_name, indent=2)
            if sp.package_name == ccid:
                found = True
        if not found:
            print(f"Could not find package named after CCID: {ccid}")
            return 1

    # display the config info before running tests
    config.log_test_info()

    # run the tester in grade mode
    if args.grade_file is not None:
        return grade()
    
    # create a regular test harness
    harness = TestHarness(config)
    success = harness.run_all(args.timeout)
    if success:
        return 0

    harness.log_failures()
    return 1

if __name__ == "__main__":
    main()
