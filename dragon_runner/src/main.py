from colorama                       import init, Fore
from dragon_runner.src.cli          import Mode, parse_cli_args, ServerArgs, ScriptArgs
from dragon_runner.src.config       import load_config
from dragon_runner.src.log          import log, log_multiline
from dragon_runner.scripts.loader   import Loader
from dragon_runner.src.server       import serve
from dragon_runner.src.harness      import * 

# initialize terminal colors
init(autoreset=True)

def main(): 
    # parse and verify the CLI arguments
    cli_args = parse_cli_args()
    log(cli_args, level=1)
    
    # run the server for running configs through HTTP
    if isinstance(cli_args, ServerArgs):
        serve(cli_args)
        return 0

    # dragon-runner can also be used as a loader for grading & other scripts
    if isinstance(cli_args, ScriptArgs):
        loader = Loader()
        return loader(cli_args.args)

    # parse and verify the config
    config = load_config(cli_args.config_file, cli_args)
    if not config:
        log(f"Could not open config file: {cli_args.config_file}")
        return 1

    if config.error_collection:
        log(f"Found Config {len(config.error_collection)} error(s):")
        log(f"Parsed {cli_args.config_file} below:")
        log_multiline(str(config), indent=2)
        log(Fore.RED + str(config.error_collection) + Fore.RESET)
        return 1

    if cli_args.verify:
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

    if cli_args.mode == Mode.REGULAR:
        # run in regular mode
        harness = RegularHarness(config, cli_args)

    elif cli_args.mode == Mode.TOURNAMENT:
        # run the tester in tournament mode
        harness = TournamentHarness(config, cli_args)

    elif cli_args.mode == Mode.MEMCHECK:
        # check tests for memory leaks
        harness = MemoryCheckHarness(config, cli_args)

    elif cli_args.mode == Mode.PERF:
        # performance testing
        harness = PerformanceTestingHarness(config, cli_args) 
    else:
        raise RuntimeError(f"Failed to provide valid mode: {cli_args.mode}")
    
    success = harness.run()
    if success:
        return 0
    return 1

if __name__ == "__main__":
    main()
        
