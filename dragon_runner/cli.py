import argparse
import os
from typing import NamedTuple

class CLIArgs(NamedTuple):
    config_file: str
    grade_file: str
    failure_log: str
    timeout: float
    debug_package: str
    time: bool
    verbosity: int
    verify: bool
    restore: bool
    restore_file: str

    def __repr__(self) -> str:
        return (
            "Parsed CLI Arguments:\n"
            f"  Config File: {self.config_file}\n"
            f"  Grade File: {self.grade_file}\n"
            f"  Failure Log: {self.failure_log}\n"
            f"  Timeout: {self.timeout}\n"
            f"  Debug Package: {self.debug_package}\n"
            f"  Time: {self.time}\n"
            f"  Verbosity: {self.verbosity}"
            f"  Verify: {self.verify}\n"
            f"  Restore: {self.restore}"
            f"  Restore file: {self.restore_file}"
        )

def parse_cli_args() -> CLIArgs:
    parser = argparse.ArgumentParser(description="CMPUT 415 testing utility")

    parser.add_argument("config_file", help="Path to the tester JSON configuration file.")
    parser.add_argument("--grade", dest="grade_file", help="Perform grading analysis and output to this file")
    parser.add_argument("--log-failures", dest="failure_log", help="Log the testcases the solution compiler fails.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Specify timeout length for EACH command in a toolchain.")
    parser.add_argument("--verify", action="store_true", default=False, help="Verify that config and tests are configured correctly")
    parser.add_argument("--debug-package", help="Provide a sub-path to run the tester on.") 
    parser.add_argument("-t", "--time", action="store_true", help="Include the timings (seconds) of each test in the output.")
    parser.add_argument("-v", "--verbosity", action="count", default=0, help="Increase verbosity level")
    parser.add_argument("--restore-checkpoint", dest="restore", default=False, action="store_true", help="Restore a checkpoint from .checkpoint.json for a partially failed testing run")
    parser.add_argument("--restore-file", dest="restore_file", default=".checkpoint.json", help="Alternative checkpoint file")

    args: CLIArgs = parser.parse_args()
    if not os.path.isfile(args.config_file):
        parser.error(f"The config file {args.config_file} does not exist.")
    if bool(args.grade_file) != bool(args.failure_log):
        parser.error("Both --grade and --log-failures must be provided together.") 
    if args.verbosity > 0:
        os.environ["DEBUG"] = str(args.verbosity)

    return CLIArgs(
        config_file     = args.config_file,
        grade_file      = args.grade_file,
        failure_log     = args.failure_log,
        timeout         = args.timeout,
        debug_package   = args.debug_package,
        time            = args.time,
        verbosity       = args.verbosity,
        verify          = args.verify,
        restore         = args.restore,
        restore_file    = args.restore_file
    )

