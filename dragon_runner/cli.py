from typing import NamedTuple, List
import argparse
import os
import shlex

def parse_script_args(arg_string: str) -> List[str]:
    """
    Parse a quoted string into a list of arguments using shlex
    """
    if not arg_string:
        return []
    return shlex.split(arg_string)

class CLIArgs(NamedTuple):
    config_file: str
    output_file: str
    failure_log: str
    debug_package: str
    mode: str
    timeout: float
    time: bool
    verbosity: int
    verify: bool
    script_args: List[str]

    def __repr__(self) -> str:
        return (
            "Parsed CLI Arguments:\n"
            f"  Config File: {self.config_file}\n"
            f"  Mode: {self.mode}\n"
            f"  Failure Log: {self.failure_log}\n"
            f"  Timeout: {self.timeout}\n"
            f"  Debug Package: {self.debug_package}\n"
            f"  Time: {self.time}\n"
            f"  Output file: {self.output_file}\n"
            f"  Verbosity: {self.verbosity}\n"
            f"  Verify: {self.verify}\n"
            f"  Script Args: {' '.join(self.script_args)}"
        )

def parse_cli_args() -> CLIArgs:
    parser = argparse.ArgumentParser(description="CMPUT 415 testing utility")
    
    # Make config_file optional
    parser.add_argument("config_file", nargs="?", default=None,
        help="Path to the tester JSON configuration file (required for regular and grade modes).")
    
    parser.add_argument("--mode", dest="mode", default="regular",
        help="run in regular, grade or script mode")
    
    parser.add_argument("--script-args", type=parse_script_args, default=[],
        help='Arguments to pass to the script (quote the entire string, e.g. --script-args="arg1 arg2")')
    
    parser.add_argument("--fail-log", dest="failure_log",
        help="Log the testcases the solution compiler fails.")
    
    parser.add_argument("--timeout", type=float, default=2.0,
        help="Specify timeout length for EACH command in a toolchain.")
    
    parser.add_argument("--verify", action="store_true", default=False,
        help="Verify that config and tests are configured correctly")
    
    parser.add_argument("--debug-package",
        help="Provide a sub-path to run the tester on.") 
    
    parser.add_argument("-t", "--time", action="store_true",
        help="Include the timings (seconds) of each test in the output.")
    
    parser.add_argument("-v", "--verbosity", action="count", default=0,
        help="Increase verbosity level")
    
    parser.add_argument("-o", "--output", metavar="FILE",
        help="Direct the output of dragon-runner to FILE")

    args = parser.parse_args()
    
    # Check if config file is required based on mode
    if args.mode in ["regular", "grade"]:
        if not args.config_file:
            parser.error(f"Config file is required for {args.mode} mode")
        if not os.path.isfile(args.config_file):
            parser.error(f"The config file {args.config_file} does not exist.")
    if args.mode == "grade" and (not bool(args.failure_log) or not bool(args.output)):
        parser.error("Failure log and ouput file must be supplied when using grade mode.") 
    
    if args.verbosity > 0:
        os.environ["DEBUG"] = str(args.verbosity)
    
    return CLIArgs(
        config_file    = args.config_file,
        mode          = args.mode,
        failure_log   = args.failure_log,
        timeout       = args.timeout,
        debug_package = args.debug_package,
        output_file   = args.output,
        time          = args.time,
        verbosity     = args.verbosity,
        verify        = args.verify,
        script_args   = args.script_args
    )
