from colorama               import init, Fore
from dragon_runner.cli      import parse_cli_args, CLIArgs
from dragon_runner.config   import load_config
from dragon_runner.log      import log, log_multiline
from dragon_runner.scripts.loader import Loader 
from dragon_runner.harness  import MemoryCheckHarness, PerformanceTestingHarness, \
                                   RegularHarness, TournamentHarness

# initialize terminal colors
init(autoreset=True)

def main(): 
    # parse and verify the CLI arguments
    args: CLIArgs = parse_cli_args()
    log(args, level=1)
    
    # dragon-runner can also be used as a loader for grading & other scripts
    if args.is_script_mode():
        print(f"Use dragon-runner as a loader for script: {args.mode}")
        loader = Loader(args.mode, args.script_args)
        loader.run() 
        return 0

    # parse and verify the config
    config = load_config(args.config_file, args)
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
        ccid = input("Enter your CCID/Github Team Name: ")
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
    
    if args.mode == "regular":
        # run in regular mode
        harness = RegularHarness(config, args)

    elif args.mode == "tournament":
        # run the tester in tournament mode
        harness = TournamentHarness(config, args)

    elif args.mode == "memcheck":
        # check tests for memory leaks
        harness = MemoryCheckHarness(config, args)

    elif args.mode == "perf":
        # performance testing
        harness = PerformanceTestingHarness(config, args) 
    
    else:
        raise RuntimeError(f"Failed to provide valid mode: {args.mode}")
    
    success = harness.run()
    harness.post_run_log()
    if success:
        return 0
    return 1

if __name__ == "__main__":
    main()
        
