import subprocess
import os
import re
import json
import time
from subprocess                 import TimeoutExpired, CompletedProcess
from io                         import BytesIO
from typing                     import List, Dict, Optional, Union
from dataclasses                import dataclass, asdict
from difflib                    import Differ
from colorama                   import Fore, init
from dragon_runner.testfile     import TestFile 
from dragon_runner.config       import Executable, ToolChain
from dragon_runner.log          import log
from dragon_runner.utils        import make_tmp_file, bytes_to_str, file_to_bytes
from dragon_runner.toolchain    import Step

init(autoreset=True)

class ToolChainResult:
    def __init__(self, success: bool, result: Union[CompletedProcess, BytesIO], 
                                      last_step: Step, time=0):
        """
        Result produced by running the toolchain for a single (exe, test) pair 
        """        
        self.success: bool          = success
        self.last_step: Step        = last_step
        self.time: float            = time
        self.stderr, self.stdout    = BytesIO(b''), BytesIO(b'') #default no output 
        self.exit_code              = 255 # default non-zero exit
        
        if isinstance(result, CompletedProcess):
            self.stdout: BytesIO    = BytesIO(result.stdout) if result else BytesIO(b'')                
            self.stderr: BytesIO    = BytesIO(result.stderr) if result else BytesIO(b'')
            self.exit_code: int     = result.returncode if result else 255
        elif isinstance(result, BytesIO):
            self.stdout     = result
            self.exit_code  = 0
  
    @classmethod
    def from_output_bytes(cls, out_bytes: BytesIO, last_step: Step, time=0):
        """
        Alternative constructor from bytes rather than subprocess result
        """
        return cls(True, out_bytes, last_step, time)

@dataclass
class MagicParams:
    exe_path: str       # $EXE
    input_file: str     # $INPUT
    output_file: str    # $OUTPUT 
    def __repr__(self):
        return json.dumps(asdict(self), indent=2)

@dataclass
class TestResult:
    did_pass: bool
    error_test: bool
    time: Optional[float] = 0
    diff: Optional[str] = None
    def __repr__(self):
        return json.dumps(asdict(self), indent=2)

@dataclass
class Command:
    args: List[str] 
    def log(self, level:int=0):
        log("Command: ", ' '.join(self.args), indent=2, level=level)

@dataclass
class CommandResult:
    subprocess: Optional[CompletedProcess]
    exit_status: int 
    time: float=0
    timed_out: bool=False

    def log(self, level:int=0):
        if self.subprocess:
            stdout = self.subprocess.stdout
            stderr = self.subprocess.stderr
            log(f"stdout ({len(stdout)} bytes):", stdout, indent=4, level=level)
            log(f"stderr ({len(stderr)} bytes):", stderr, indent=4, level=level)
            log(f"exit code: {self.exit_status}", indent=4, level=level)

@dataclass
class TestResult:
    did_pass: bool
    error_test: bool
    time: Optional[float]=0
    diff: Optional[str]=None

class ToolChainRunner():
    def __init__(self, tc: ToolChain, timeout: float, env: Dict[str, str]={}):
        self.tc         = tc
        self.timeout    = timeout
        self.env        = env

    def run_command(self, command: Command, stdin: BytesIO) -> CommandResult:
        """
        execute a resolved command
        """        
        env = os.environ.copy()
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE
        input_bytes = stdin.getvalue()

        start_time = time.time()
        try:
            result = subprocess.run(command.args, env=env, input=input_bytes, stdout=stdout,
                                    stderr=stderr, check=False, timeout=self.timeout)
            wall_time = time.time() - start_time
            return CommandResult(subprocess=result, exit_status=result.returncode, time=wall_time, timed_out=False)
        except TimeoutExpired:
            return CommandResult(subprocess=None, exit_status=255, time=0, timed_out=True)
        
    def resolve_output_file(self, step: Step) -> str:
        """
        make absolute path from output file in step
        """
        current_dir = os.getcwd()
        output_file = os.path.join(current_dir, step.output) if step.output else None
        return output_file
    
    def resolve_command(self, step: Step, params: MagicParams) -> Command:
        """
        replace magic parameters with real arguments
        """
        command = Command([step.exe_path] + step.arguments)
        command = self.replace_magic_args(command, params)
        command = self.replace_env_vars(command)
        exe = command.args[0]
        if not os.path.isabs(exe):
            command.args[0] = os.path.abspath(exe)
        return command
    
    def run(self, test: TestFile, exe: Executable) -> ToolChainResult: 
        """
        run each step of the toolchain for a given test and executable
        """
        input_file = test.path

        for index, step in enumerate(self.tc):
            last_step       = index == len(self.tc) - 1
            input_stream    = test.get_input_stream() if step.uses_ins else BytesIO(b'')
            output_file     = self.resolve_output_file(step) 
            command         = self.resolve_command(step, MagicParams(exe.exe_path, input_file, output_file))
            command_result  = self.run_command(command, input_stream)

            command.log(level=2)
            command_result.log(level=2)

            tc_result: Optional[ToolChainResult] = None
            if command_result.timed_out:
                return ToolChainResult(success=False, result=None, last_step=step, time=0)

            elif command_result.subprocess.returncode != 0:
                return ToolChainResult(success=step.allow_error, result=command_result.subprocess,
                                                    last_step=step, time=0)

            elif last_step and output_file is not None:
                if not os.path.exists(output_file):
                    raise RuntimeError(f"Command did not create specified output file {output_file}")

                output_file_contents = file_to_bytes(output_file)
                tc_result = ToolChainResult(success=True, result=output_file_contents, last_step=step,
                                                    time=command_result.time)
            
            elif last_step and output_file is None:
                tc_result = ToolChainResult(success=True, result=command_result.subprocess, last_step=step,
                                                    time=command_result.time)
            else: 
                # set up the next steps input file
                input_file = output_file or make_tmp_file(BytesIO(command_result.subprocess.stdout))
        return tc_result

    @staticmethod
    def replace_env_vars(cmd: Command) -> Command:
        """
        Expand environment variables with the values from current shell
        """   
        resolved = []
        for arg in cmd.args:
            matches = re.findall(r'\$(\w+)|\$\{(\w+)\}', arg)
            if matches:
                for match in matches:
                    var_name = match[0] or match[1]
                    env_value = os.environ.get(var_name)
                    if env_value is not None: 
                        arg = arg.replace(f"${var_name}", env_value)\
                                .replace(f"${{{var_name}}}", env_value) 
                resolved.append(arg)
            else:
                resolved.append(arg)
        return Command(resolved)

    @staticmethod
    def replace_magic_args(command: Command, params: MagicParams) -> Command:
        """
        Magic args are inherited from previous steps
        """
        resolved = []
        for arg in command.args:
            if arg == '$EXE':
                resolved.append(params.exe_path)
            elif arg == '$INPUT':
                resolved.append(params.input_file)
            elif arg == '$OUTPUT':
                resolved.append(params.output_file) 
            else:
                resolved.append(arg)
        return Command(resolved)

def get_test_result(tc_result: ToolChainResult, expected_out: BytesIO) -> TestResult:
    """
    Determine the test result based on ToolChainResult and expected output.
    Result Rules:
        (T,F) If tc successful, exit is zero and precise diff on stdout
        (T,T) If tc successful, exit non zero and a lenient diff on stderr succeeds
        (F,T) If tc successful, exit non zero and all lenient diffs on stderr fail
        (F,F) If tc not successful
    """
    # define capture patterns for lenient diff
    compile_time_pattern = r'.*?(Error on line \d+):?.*' 
    runtime_pattern = r'\s*(\w+Error):?.*'

    if tc_result.success:
        if tc_result.exit_code == 0:
            # Regular test: Take precise diff from only stdout
            diff = precise_diff(tc_result.stdout, expected_out)
            if not diff: 
                return TestResult(did_pass=True, error_test=False, time=tc_result.time)
            else:
                return TestResult(did_pass=False, error_test=False)
        else:
            # Error Test: Take lenient diff from only stderr 
            ct_diff = lenient_diff(tc_result.stderr, expected_out, compile_time_pattern)
            rt_diff = lenient_diff(tc_result.stderr, expected_out, runtime_pattern)
            if not ct_diff:
                return TestResult(did_pass=True, error_test=True)
            elif not rt_diff:
                return TestResult(did_pass=True, error_test=True)
            else:
                return TestResult(did_pass=False, error_test=True, diff=ct_diff)
    else:
        return TestResult(did_pass=False, error_test=True, diff="")

def precise_diff(produced: BytesIO, expected: BytesIO) -> str:
    """
    Return the difference of two byte strings, otherwise empty string 
    """
    produced_str = bytes_to_str(produced)
    expected_str = bytes_to_str(expected)

    # identical strings implies no diff 
    if produced_str == expected_str:
        return ""

    differ = Differ()
    diff = list(differ.compare(produced_str.splitlines(), expected_str.splitlines()))
    return color_diff(diff)

def lenient_diff(produced: BytesIO, expected: BytesIO, pattern: str) -> str:
    """
    Perform a lenient diff on error messages, using the pattern as a mask/filter.
    """
    produced_str = bytes_to_str(produced).strip()
    expected_str = bytes_to_str(expected).strip()
    
    # Apply the mask/filter to both strings
    produced_masked = re.sub(pattern, r'\1', produced_str, flags=re.IGNORECASE | re.DOTALL)
    expected_masked = re.sub(pattern, r'\1', expected_str, flags=re.IGNORECASE | re.DOTALL)

    # If the masked strings are identical, return an empty string (no diff)
    if produced_masked == expected_masked:
        return ""

    # If the masked strings are different, generate a diff
    differ = Differ()
    diff = list(differ.compare(produced_masked.splitlines(), expected_masked.splitlines()))
    return color_diff(diff)

def color_diff(diff_lines: list) -> str:
    """
    Returns a colored string representation of the diff.
    """
    if not diff_lines:
        return "No differences found."
    colored_lines = []
    for line in diff_lines:
        if line.startswith('+'):
            colored_lines.append(Fore.GREEN + line)
        elif line.startswith('-'):
            colored_lines.append(Fore.RED + line)
        elif line.startswith('?'):
            colored_lines.append(Fore.CYAN + line)
        else:
            colored_lines.append(Fore.RESET + line)
    return '\n'.join(colored_lines)
