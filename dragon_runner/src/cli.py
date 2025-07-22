from pathlib import Path
from typing import Any, NamedTuple, List
from dragon_runner.scripts.loader import Loader 
from enum import Enum
import argparse
from enum import Enum
from typing import List, NamedTuple, Protocol, runtime_checkable
from pathlib import Path
import argparse
import sys
import os

class Mode(Enum):
    REGULAR = "regular"
    TOURNAMENT = "tournament"
    PERF = "perf"
    MEMCHECK = "memcheck"
    SERVE = "serve"
    SCRIPT = "script"

@runtime_checkable
class CLIArgs(Protocol):
    mode: Mode

class RunnerArgs(NamedTuple):
    mode: Mode
    config_file: str = ""
    output: str = ""
    failure_log: str = ""
    debug_package: str = ""
    timeout: float = 2.0
    time: bool = False
    verbosity: int = 0
    verify: bool = False
    show_testcase: bool = False
    fast_fail: bool = False

class ScriptArgs(NamedTuple):
    mode: Mode
    script_file: str
    script_args: List[str] = []

class ServerArgs(NamedTuple):
    mode: Mode
    port: int = 5000
    serve_path: Path = Path(".")

def parse_runner_args(argv_skip: int=1) -> RunnerArgs:
    parser = argparse.ArgumentParser(description="CMPUT 415 testing utility")
    
    parser.add_argument("config_file", help="Path to the JSON configuration file")
    parser.add_argument("--fail-log", dest="failure_log", default="")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--debug-package", default="")
    parser.add_argument("-t", "--time", action="store_true")
    parser.add_argument("-v", "--verbosity", action="count", default=0)
    parser.add_argument("-s", "--show-testcase", action="store_true")
    parser.add_argument("-o", "--output", default="")
    parser.add_argument("-f", "--fast-fail", dest="fast_fail", action="store_true")
    
    # Parse arguments
    args = parser.parse_args(sys.argv[argv_skip:])
    
    # Set debug environment variable 
    os.environ["DRAGON_RUNNER_DEBUG"] = str(args.verbosity)
    
    # Convert to dictionary and add mode
    args_dict = vars(args)
    args_dict["mode"] = Mode.REGULAR
    
    return RunnerArgs(**args_dict)

def parse_script_args() -> ScriptArgs:
    if len(sys.argv) == 2:
        print("Script file required")
        sys.exit(1)
    elif len(sys.argv) < 3:
        print("Usage: dragon-runner script <script_file> [script_args...]")
        sys.exit(1)
        
    return ScriptArgs(
        mode=Mode.SCRIPT,
        script_file=sys.argv[2],
        script_args=sys.argv[3:]
    )

def parse_server_args() -> ServerArgs:
    parser = argparse.ArgumentParser(description="Server mode")
    parser.add_argument("serve_path", type=Path, help="Config directory or file")
    parser.add_argument("--port", type=int, default=5000)
    
    args = parser.parse_args(sys.argv[2:])
    return ServerArgs(
        mode=Mode.SERVE,
        port=args.port,
        serve_path=args.serve_path
    )

def parse_cli_args() -> Any:
    if len(sys.argv) < 2:
        print("Usage: dragon-runner [mode] config.json [args...]")
        print("  mode: [regular|tournament|perf|memcheck|serve|script])")
        print("  args: dragon-runner -h")
        sys.exit(1)
        
    first_arg = sys.argv[1]
    
    # Create a mapping to convert string to Mode enum
    mode_map = {mode.value: mode for mode in Mode}
    
    if first_arg in mode_map:
        if first_arg == Mode.SERVE.value:
            return parse_server_args()
        elif first_arg == Mode.SCRIPT.value:
            return parse_script_args()
        else:
            # For runner modes
            args = parse_runner_args(argv_skip=2)
            return RunnerArgs(**{**args._asdict(), "mode": mode_map[first_arg]})
    else:
        # If no mode is supplied, default to regular mode
        return parse_runner_args(1)

