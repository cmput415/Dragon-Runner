import subprocess
import os
import re
import json
import time
import sys
from subprocess                 import TimeoutExpired, CompletedProcess
from io                         import BytesIO
from typing                     import List, Dict, Optional
from dataclasses                import dataclass, asdict
from colorama                   import Fore, init
from dragon_runner.testfile     import TestFile 
from dragon_runner.config       import Executable, ToolChain
from dragon_runner.log          import log, log_delimiter, log_multiline
from dragon_runner.utils        import make_tmp_file, bytes_to_str, file_to_bytes
from dragon_runner.toolchain    import Step

init(autoreset=True)

@dataclass
class MagicParams:
    exe_path: str       # $EXE
    input_file: str     # $INPUT
    output_file: str    # $OUTPUT 
    def __repr__(self):
        return json.dumps(asdict(self), indent=2)

@dataclass
class Command:
    args: List[str] 
    def log(self, level:int=0):
        log("Command: ", ' '.join(self.args), indent=4, level=level)

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
    __test__ = False                    # pytest gets confused when classes start with 'Test'
    test: TestFile                      # test result is derived from 
    did_pass: bool                      # did expected out match generated
    error_test: bool=False              # did test return with non-zero exit
    did_panic: bool=False               # did test cause the toolchain to panic
    time: Optional[float]=None          # time test took on the final step
    diff: Optional[str]=None            # diff if the test failed gracefully
    error_msg: Optional[str]=None       # error message if test did not fail gracefully
    failing_step: Optional[str]=None    # step the TC failed on
    gen_output: Optional[bytes]=None    # output of the test

    def log(self, file=sys.stderr):
        if self.did_pass:
            pass_msg = "[E-PASS] " if self.error_test else "[PASS] "
            log(Fore.GREEN + pass_msg + Fore.RESET + f"{self.test.file}", indent=2, file=file)
        else:
            fail_msg = "[E-FAIL] " if self.error_test else "[FAIL] "
            log(Fore.RED + fail_msg + Fore.RESET + f"{self.test.file}", indent=2, file=file)

        level = 3 if self.did_pass else 2
        log(f"==> Expected Out ({self.test.expected_out_bytes} bytes):", indent=4, level=level)
        log_multiline(self.test.expected_out, level=level, indent=6)
        log(f"==> Generated Out ({len(self.gen_output)} bytes):", indent=4, level=level)
        log_multiline(self.gen_output, level=level, indent=6)

class ToolChainRunner():
    def __init__(self, tc: ToolChain, timeout: float, env: Dict[str, str]={}):
        self.tc         = tc
        self.timeout    = timeout
        self.env        = env

    def run_command(self, command: Command, stdin: bytes) -> CommandResult:
        """
        execute a resolved command
        """
        assert isinstance(stdin, bytes), "parameter type check"
        env = os.environ.copy()
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE

        start_time = time.time()
        try:
            result = subprocess.run(command.args, env=env, input=stdin, stdout=stdout,
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
    
    def run(self, test: TestFile, exe: Executable) -> TestResult: 
        """
        run each step of the toolchain for a given test and executable
        """
        input_file = test.path

        for index, step in enumerate(self.tc):
            last_step       = index == len(self.tc) - 1
            input_stream    = test.get_input_stream() if step.uses_ins else b'' 
            output_file     = self.resolve_output_file(step) 
            command         = self.resolve_command(step, MagicParams(exe.exe_path, input_file, output_file))
            command_result  = self.run_command(command, input_stream)

            command.log(level=3)
            command_result.log(level=3)

            if command_result.timed_out:
                timeout_msg = f"Toolchain timed out for test: {test.file}"
                return TestResult(test=test, did_pass=False, did_panic=True, error_test=False,
                                  gen_output=b'', failing_step=step.name, error_msg=timeout_msg)
            
            child_process : CompletedProcess = command_result.subprocess
            if not child_process:
                raise RuntimeError(f"Command {exe.exe_path} could not spawn child process")

            elif child_process.returncode != 0:
                if step.allow_error:
                    return self.get_test_result(test, child_process, test.expected_out)
                return TestResult(test=test, did_pass=False, error_test=False,
                                  failing_step=step.name, gen_output=child_process.stderr)

            elif last_step:
                if output_file and not os.path.exists(output_file):
                    raise RuntimeError(f"Command did not create specified output file {output_file}")

                if output_file is not None:
                    output_file_contents = file_to_bytes(output_file)
                    child_process.stdout = output_file_contents

                return self.get_test_result(test, child_process, test.expected_out)
            
            else: 
                # set up the next steps input file
                input_file = output_file or make_tmp_file(child_process.stdout)

    @staticmethod 
    def get_test_result(test: TestFile, subps_result: CompletedProcess, expected_out: bytes, time=0) -> TestResult:
        """
        Determine the test result based on ToolChainResult and expected output.
        Result Rules:
            (T,F) If tc successful, exit is zero and precise diff on stdout
            (T,T) If tc successful, exit non zero and a lenient diff on stderr succeeds
            (F,T) If tc successful, exit non zero and all lenient diffs on stderr fail
            (F,F) If tc not successful
        """
        assert isinstance(subps_result.stdout, bytes) and isinstance(expected_out, bytes), "test result received non-bytes"

        # define capture patterns for lenient diff
        compile_time_pattern = r'.*?(Error on line \d+):?.*' 
        runtime_pattern = r'\s*(\w+Error):?.*'
        
        generated_stdout = subps_result.stdout
        generated_stderr = subps_result.stderr

        if subps_result.returncode == 0:
            # Regular test: Take precise diff from only stdout
            diff = precise_diff(generated_stdout, expected_out)
            if not diff: 
                return TestResult(test=test, did_pass=True, error_test=False, time=time,
                                  gen_output=generated_stdout)
            else:
                return TestResult(test=test, did_pass=False, error_test=False,
                                  failing_step="stdout diff", gen_output=generated_stdout)
        else:
            # Error Test: Take lenient diff from only stderr 
            ct_diff = lenient_diff(generated_stderr, expected_out, compile_time_pattern)
            rt_diff = lenient_diff(generated_stderr, expected_out, runtime_pattern)
            if not ct_diff:
                return TestResult(test=test, did_pass=True, error_test=True,
                                  gen_output=generated_stderr)
            elif not rt_diff:
                return TestResult(test=test, did_pass=True, error_test=True,
                                  gen_output=generated_stderr)
            else:
                return TestResult(test=test, did_pass=False, error_test=True, diff=ct_diff,
                                  failing_step="stderr diff", gen_output=generated_stderr)

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

def diff_bytes(s1: bytes, s2: bytes):
    """
    The difflib library appears to have an infinite recursion bug.
    It is simple to write our own.
    """
    result = []
    i, j = 0, 0
    while i < len(s1) and j < len(s2):
        if s1[i] != s2[j]:
            result.append(f"-{s1[i]}")
            result.append(f"+{s2[j]}")
        else:
            result.append(f" {s1[i]}")
        i += 1
        j += 1
    while i < len(s1):
        result.append(f"-{s1[i]}")
        i += 1
    while j < len(s2):
        result.append(f"+{s2[j]}")
        j += 1 
    return ''.join(result)

def precise_diff(produced: bytes, expected: bytes) -> str:
    """
    Return the difference of two byte strings, otherwise empty string 
    """
    # identical strings implies no diff 
    if produced == expected:
        return ""
    return diff_bytes(produced, expected)

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
    return diff_bytes(produced_str, expected_str)

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
