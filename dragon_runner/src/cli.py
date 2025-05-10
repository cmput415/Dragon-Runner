from pathlib import Path
from typing import NamedTuple, List
from dragon_runner.scripts.loader import Loader 
from enum import Enum
import argparse
import sys
import os

class Mode(Enum):
    REGULAR = 0,
    TOURNAMENT = 1,
    PERF = 2,
    MEMCHECK = 3,
    SERVE = 4,
    SCRIPT = 5 

class RunnerCLIArgs(NamedTuple):
    config_file: str = ""
    output: str = ""
    failure_log: str = ""
    debug_package: str = ""
    mode: str = "regular"
    timeout: float = 2.0
    time: bool = False
    verbosity: int = 0
    verify: bool = False
    show_testcase: bool = False

class CLIArgs(NamedTuple):
    config_file: str = ""
    output: str = ""
    failure_log: str = ""
    debug_package: str = ""
    mode: str = "regular"
    timeout: float = 2.0
    time: bool = False
    verbosity: int = 0
    verify: bool = False
    show_testcase: bool = False
    script_file: str = ""
    script_args: List[str] = []
    
    def is_script_mode(self):
        return self.script_file != ""

    def __repr__(self) -> str:
        return (
            "Parsed CLI Arguments:\n"
            f"  Config File: {self.config_file}\n"
            f"  Mode: {self.mode}\n"
            f"  Failure Log: {self.failure_log}\n"
            f"  Timeout: {self.timeout}\n"
            f"  Debug Package: {self.debug_package}\n"
            f"  Time: {self.time}\n"
            f"  Output file: {self.output}\n"
            f"  Verbosity: {self.verbosity}\n"
            f"  Verify: {self.verify}\n"
            f"  Script Args: {' '.join(self.script_args)}"
        )

# class ServerCLIArgs(CLIArgs):
#     # TODO: Implement a scheme for inheriting CLIArgs
#     def __init__(self, *args, **kwargs):
#         super().__init__(args) 
#         serve_dir: Path = kwargs.get("serve_dir", ".") 
#         
def parse_runner_args(argv_start: int = 1) -> CLIArgs:

    parser = argparse.ArgumentParser(description="CMPUT 415 testing utility")
    
    parser.add_argument("config_file", help="Path to the JSON configuration file")
    parser.add_argument("--fail-log", dest="failure_log")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--debug-package")
    parser.add_argument("-t", "--time", action="store_true")
    parser.add_argument("-v", "--verbosity", action="count", default=0)
    parser.add_argument("-s", "--show-testcase", action="count", default=0)
    parser.add_argument("-o", "--output")
    
    # Parse arguments
    args = parser.parse_args(sys.argv[argv_start:])
    
    # Set debug environment variable 
    os.environ["DRAGON_RUNNER_DEBUG"] = str(args.verbosity)

    return CLIArgs(**vars(args))

def parse_script_args() -> CLIArgs:
    if len(sys.argv) == 2:
        print(Loader().__repr__()) 
        sys.exit(1)
    elif len(sys.argv) < 3:
        print("Usage: dragon-runner script <script_file> [script_args...]")
        sys.exit(1)
        
    return CLIArgs(
        mode="script",
        script_file=sys.argv[2],
        script_args=sys.argv[3:]
    )

def parse_server_args() -> CLIArgs:
    print("Usage: dragon-runnner serve <config_dir|config>")
    return CLIArgs(mode="serve")

def parse_cli_args() -> CLIArgs:
    if len(sys.argv) < 2:
        print("Usage: dragon-runner [mode] config.json [args...]")
        print("  mode: [regular|tournament|perf|memcheck|serve|script])")
        print("  args: dragon-runner -h")
        sys.exit(1)

    first_arg = sys.argv[1]
    
    if first_arg in ["tournament", "perf", "memcheck"]:
        args = parse_runner_args(2)
        return args._replace(mode=first_arg)
    elif first_arg == "script":
        return parse_script_args()
    elif first_arg == "serve":
        return parse_server_args()
    else:
        return parse_runner_args(1)

