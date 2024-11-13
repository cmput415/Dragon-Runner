import subprocess
import os
import re
import json
import time
import sys
from subprocess                 import TimeoutExpired, CompletedProcess
from typing                     import List, Dict, Optional, Union
from dataclasses                import dataclass, asdict
from colorama                   import Fore, init
from dragon_runner.testfile     import TestFile 
from dragon_runner.config       import Executable, ToolChain
from dragon_runner.log          import log, log_multiline
from dragon_runner.utils        import make_tmp_file, bytes_to_str,\
                                       file_to_bytes, str_to_bytes, truncated_bytes
from dragon_runner.toolchain    import Step
from dragon_runner.cli          import CLIArgs

init(autoreset=True)

@dataclass
class MagicParams:
    exe_path: str                       # $EXE
    input_file: Optional[str] = ""      # $INPUT
    output_file: Optional[str] = ""     # $OUTPUT 
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
            log(f"stdout ({len(stdout)} bytes):", truncated_bytes(stdout, max_bytes=512), indent=4, level=level)
            log(f"stderr ({len(stderr)} bytes):", truncated_bytes(stderr, max_bytes=512), indent=4, level=level)
            log(f"exit code: {self.exit_status}", indent=4, level=level)

@dataclass
class TestResult: 
    __test__ = False                    # pytest gets confused when classes start with 'Test'
    test: TestFile                      # test result is derived from 
    did_pass: bool=False                # did expected out match generated
    error_test: bool=False              # did test return with non-zero exit
    did_panic: bool=False               # did test cause the toolchain to panic
    time: Optional[float]=None          # time test took on the final step
    diff: Optional[str]=None            # diff if the test failed gracefully
    error_msg: Optional[str]=None       # error message if test did not fail gracefully
    failing_step: Optional[str]=None    # step the TC failed on
    gen_output: Optional[bytes]=b''     # output of the test

    def log(self, file=sys.stdout, args: Union[CLIArgs, None]=None):
        if self.did_pass:
            pass_msg = "[E-PASS] " if self.error_test else "[PASS] "
            test_name = f"{self.test.file:<50}"     
            if args and args.time and self.time is not None:
                time_str = f"{self.time:.4f}"
                time_with_unit = f"{time_str:>10} (s)" 
            else:
                time_with_unit = "" 
            log_msg = f"{Fore.GREEN}{pass_msg}{Fore.RESET}{test_name}{time_with_unit}"
            log(log_msg, indent=3, file=file)
        else:
            fail_msg = "[E-FAIL] " if self.error_test else "[FAIL] "
            log(Fore.RED + fail_msg + Fore.RESET + f"{self.test.file}", indent=3, file=file)

        level = 3 if self.did_pass else 2
        # if not self.test.expected_out:
            # return
        log(f"==> Expected Out ({len(self.test.expected_out)} bytes):", indent=5, level=level)
        log_multiline(self.test.expected_out, level=level, indent=6)
        log(f"==> Generated Out ({len(self.gen_output)} bytes):", indent=5, level=level)
        log_multiline(self.gen_output, level=level, indent=6)

    def __repr__(self):
        return "PASS" if self.did_pass else "FAIL"

class ToolChainRunner():
    def __init__(self, tc: ToolChain, timeout: float, env: Dict[str, str]={}):
        self.tc         = tc
        self.timeout    = timeout
        self.env        = env

    def run_command(self, command: Command, stdin: bytes) -> CommandResult:
        """
        execute a resolved command
        """
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
        
    def resolve_output_file(self, step: Step) -> Optional[str]:
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
    
    def run(self, test: TestFile, exe: Executable) -> Optional[TestResult]: 
        """
        run each step of the toolchain for a given test and executable
        """
        input_file = test.path
        expected = test.expected_out if isinstance(test.expected_out, bytes) else b'' 
        tr = TestResult(test=test)

        for index, step in enumerate(self.tc):

            last_step       = index == len(self.tc) - 1
            input_stream    = test.input_stream if step.uses_ins and isinstance(test.input_stream, bytes) else b'' 
            output_file     = self.resolve_output_file(step) 
            command : Command   = self.resolve_command(step, MagicParams(exe.exe_path, input_file, output_file))
            command_result : CommandResult = self.run_command(command, input_stream) 
            
            # Log command results for -vvv
            command.log(level=3)
            command_result.log(level=3)
             
            child_process = command_result.subprocess
            if not child_process:
                """
                OS failed to exec the command.
                """
                tr.did_pass = False; tr.did_panic = True;
                return tr
            
            step_stdout = child_process.stdout 
            step_stderr = child_process.stderr
            step_time = round(command_result.time, 4)

            # Check if the command timed out
            if command_result.timed_out:
                """
                A step timed out based on the max timeout specified by CLI arg.
                """
                timeout_msg = f"Toolchain timed out for test: {test.file}"
                return TestResult(test=test, did_pass=False, did_panic=True, error_test=False,
                                  gen_output=b'', failing_step=step.name, error_msg=timeout_msg)
            
            elif child_process.returncode != 0:
                """
                A step in the toolchain has returned a non-zero exit status. If "allowError"
                is specified in the config, we can perform a lenient diff based on CompileTime
                or RuntimeError message rules. Otherwise, we abort the toolchain.
                """
                tr = TestResult(test=test, gen_output=step_stderr, failing_step=step.name,
                                                                   error_test=True)
                
                # fail by default if errors are not explicitly allowed in config
                if not step.allow_error:
                    tr.did_pass = False

                # get compile time error result is not last step
                elif step.allow_error:
 
                    # Choose the compile time or runtime error pattern
                    if not last_step:
                        error_pattern = r'.*?(Error on line \d+):?.*' 
                    else:
                        error_pattern = r'\s*(\w+Error):?.*'

                    if lenient_diff(step_stderr, expected, error_pattern) == "":
                        tr.did_pass = True
                    else:
                        tr.did_pass = False
                return tr;

            elif last_step:
                """
                The last step terminated gracefully at this point. We write to the output file and
                make a precise diff to determine if the test has passed.
                """
                if output_file and not os.path.exists(output_file):
                    raise RuntimeError(f"Command did not create specified output file {output_file}")
                
                if output_file is not None:
                    output_file_contents = file_to_bytes(output_file)
                    step_stdout = output_file_contents 
                
                tr = TestResult(test=test, time=step_time, gen_output=step_stdout)
                
                # Diff the produced and expected outputs
                diff = precise_diff(child_process.stdout, expected)
                if not diff:
                    tr.did_pass = True
                else:
                    tr.did_pass = False
                return tr
 
            else:
                """
                Set up the next steps input file which is the $OUTPUT of the previous step.
                If $OUTPUT is not supplied, we create a temporary pipe.
                """
                input_file = output_file or make_tmp_file(child_process.stdout)
   
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

def diff_bytes(s1: bytes, s2: bytes) -> str:
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

def lenient_diff(produced: bytes, expected: bytes, pattern: str) -> str:
    """
    Perform a lenient diff on error messages, using the pattern as a mask/filter.
    Unfortunately we have to convert from and back to bytes in order to apply regex.
    Bytes must be UTF-8 decodable.
    """  
    produced_str = p.strip() if (p := bytes_to_str(produced)) else None
    expected_str = e.strip() if (e := bytes_to_str(expected)) else None
    
    if not produced_str or not expected_str:
        return "Failed to decode error bytes"

    # Apply the mask/filter to both strings
    produced_masked = re.sub(pattern, r'\1', produced_str, flags=re.IGNORECASE | re.DOTALL)
    expected_masked = re.sub(pattern, r'\1', expected_str, flags=re.IGNORECASE | re.DOTALL)
       
    # If the masked strings are identical, return an empty string (no diff)
    if produced_masked.lower() == expected_masked.lower(): 
        return ""

    return diff_bytes(produced, expected)

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
