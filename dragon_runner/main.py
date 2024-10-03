import os
from colorama               import init, Fore
from dragon_runner.cli      import parse_cli_args, CLIArgs
from dragon_runner.config   import load_config
from dragon_runner.log      import log, log_multiline
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
        log(f"Found Config {len(config.error_collection)} error(s):")
        log(f"Parsed {args.config_file} below:")
        log_multiline(str(config), indent=2)
        log(Fore.RED + str(config.error_collection) + Fore.RESET)
        return 1

    if args.verify:
        ccid = input("Enter your CCID: ")
        assert config and not config.error_collection
        found = False
        for pkg in config.packages:
            log("Searching.. ", pkg.name, indent=2)
            if pkg.name == ccid:
                found = True
        if not found:
            print(f"Could not find package named after CCID: {ccid}")
            return 1

    # display the config info before running tests
    config.log_test_info()
    
    # create a regular test harness
    harness = TestHarness(config, args)
    success = harness.run()
    if success:
        return 0

    harness.log_failures()
    return 1

if __name__ == "__main__":
    main()
