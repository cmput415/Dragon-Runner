import subprocess
import os
import re
import json
import time
import sys
from subprocess                     import CompletedProcess
from typing                         import List, Dict, Optional, Union
from dataclasses                    import dataclass, asdict
from colorama                       import Fore, init
from dragon_runner.src.testfile     import TestFile 
from dragon_runner.src.config       import Executable, ToolChain
from dragon_runner.src.log          import log, log_multiline
from dragon_runner.src.toolchain    import Step
from dragon_runner.src.cli          import CLIArgs
from dragon_runner.src.utils        import make_tmp_file, bytes_to_str,\
                                       file_to_bytes, truncated_bytes,\
                                       file_to_str
# Terminal colors
init(autoreset=True)

# Reserve a specific status code to use for valgrind
VALGRIND_EXIT_CODE = 111

@dataclass
class MagicParams:
    exe_path: str                       # $EXE
    input_file: Optional[str] = ""      # $INPUT
    output_file: Optional[str] = ""     # $OUTPUT 
    def __repr__(self):
        return json.dumps(asdict(self), indent=2)

class Command:
    """
    Wrapper for a list of arguments to run fork/exec style
    """
    def __init__(self, args):
        self.args: List[str]    = args
        self.cmd: str           = self.args[0] 

@dataclass
class CommandResult:
    cmd:str
    subprocess: Optional[CompletedProcess]=None
    exit_status: int=0 
    time: float=0
    timed_out: bool=False

    def log(self, level:int=0, indent=0):
        if self.subprocess:
            stdout = self.subprocess.stdout
            stderr = self.subprocess.stderr
            
            if stderr is None:
                stderr = b''
            if stdout is None:
                stdout = b''

            log(f"==> {self.cmd} (exit {self.exit_status})", indent=indent, level=level) 
            log(f"stdout ({len(stdout)} bytes):", truncated_bytes(stdout, max_bytes=512),
                indent=indent+2, level=level) 
            log(f"stderr ({len(stderr)} bytes):", truncated_bytes(stderr, max_bytes=512),
                indent=indent+2, level=level)

class TestResult:
    """
    Represents the result of running a test case, including pass/fail status,
    execution time, and error information.
    """
    __test__ = False  # pytest gets confused when classes start with 'Test' 
    def __init__(self, test:TestFile, did_pass:bool=False): 
        # required fields 
        self.test = test
        self.did_pass: bool = did_pass
        self.did_timeout: bool = False 
        self.error_test: bool = False
        self.memory_leak: bool = False
        self.command_history: List[CommandResult] = []

        # optional fields
        self.gen_output: Optional[bytes] = None
        self.time: Optional[float] = None
        self.failing_step: Optional[str] = None

    def log(self, file=sys.stdout, args: Union['CLIArgs', None]=None):
        """
        Print a TestResult to the log with various levels of verbosity.
        This is the main output the user is concerned with.
        """
        # TODO: This is very messy. Find some time to clean in up!
        pass_msg = "[E-PASS] " if self.error_test else "[PASS] "
        fail_msg = "[E-FAIL] " if self.error_test else "[FAIL] "
        timeout_msg = "[TIMEOUT] "

        test_name = f"{self.test.file:<50}"    
        show_time = args and args.time and self.time is not None
        if self.did_timeout:
            log(Fore.YELLOW + timeout_msg + Fore.RESET + f"{test_name.strip()}", indent=4, file=file)
         
        # Log test result
        elif self.did_pass:
            time_display = "" 
            if show_time:
                time_str = f"{self.time:.4f}"
                time_display = f"{time_str:>10} (s)" 
            log_msg = f"{Fore.GREEN}{pass_msg}{Fore.RESET}{test_name}{time_display}"
            log(log_msg, indent=4, file=file)
        else:
            log(Fore.RED + fail_msg + Fore.RESET + f"{test_name}", indent=4, file=file)
    
        # Log testcase
        if args and args.show_testcase:
            content = self.test.pretty_print()
            level = 1 if self.did_pass else 0
            log_multiline(content, indent=6, level=level)

        # Log the command history
        level = 3 if self.did_pass else 2
        log(f"==> Command History", indent=6, level=level)
        for cmd in self.command_history:
            cmd.log(level=level, indent=8)
        
        # Log test expected and generated
        expected_out = self.test.get_expected_out()
        generated_out = x if (x := self.gen_output) else b''
            
        log(f"==> Expected Out ({len(expected_out)} bytes):", indent=6, level=level-1)
        log(str(expected_out), level=level-1, indent=7)
        log(f"==> Generated Out ({len(generated_out)} bytes):", indent=6, level=level-1)
        log(str(generated_out), level=level-1, indent=7) 
        
    def __repr__(self):
        return "PASS" if self.did_pass else "FAIL"
    
class ToolChainRunner():
    def __init__(self, tc: ToolChain, timeout: float, env: Dict[str, str]={}):
        self.tc                     = tc
        self.timeout                = timeout
        self.env                    = env
        self.reserved_exit_codes    = [VALGRIND_EXIT_CODE]

    def run_command(self, command, stdin: bytes):
        """
        Run a command and return the CommandResult
        """
        env = os.environ.copy()
        start_time = time.time()
        cr = CommandResult(cmd=command.cmd)
        try:
            result = subprocess.run(
                command.args,
                env=env,
                input=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout
            )
            wall_time = time.time() - start_time
            cr.subprocess = result
            cr.exit_status = result.returncode 
            cr.time = wall_time
        except subprocess.TimeoutExpired:
            cr.time = self.timeout
            cr.timed_out = True
            cr.exit_status = 255
        except Exception:
            cr.exit_status = 1
        return cr
        
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
        command = Command(args=[step.exe_path] + step.arguments)
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
        expected = test.expected_out if isinstance(test.expected_out, bytes) else b'' 
        tr = TestResult(test=test, did_pass=False)
        
        for index, step in enumerate(self.tc):
            
            # set up input and output
            last_step = (index == len(self.tc) - 1) 
            input_stream = test.get_input_stream() if step.uses_ins else b''
            output_file = self.resolve_output_file(step)
            
            # resolve magic parameters for currents step
            magic_params = MagicParams(exe.exe_path, input_file, output_file)
            command = self.resolve_command(step, magic_params)
            command_result  = self.run_command(command, input_stream) 
            
            # save command history for logging
            tr.command_history.append(command_result)
 
            # Check if the command timed out
            if command_result.timed_out:
                """
                A step timed out based on the max timeout specified by CLI arg.
                """
                tr.did_pass=False;
                tr.did_timeout=True
                tr.failing_step=step.name;
                tr.time = self.timeout
                return tr
            
            child_process = command_result.subprocess
            if not child_process:
                """
                OS failed to exec the command.
                """
                tr.did_pass = False;
                return tr
            
            step_stdout = bytes(child_process.stdout) or b''
            step_stderr = bytes(child_process.stderr) or b''
            step_time = round(command_result.time, 4) 
            
            if child_process.returncode in self.reserved_exit_codes:
                """
                Special case for reserved exit codes
                1) Valgrind
                """
                if child_process.returncode == VALGRIND_EXIT_CODE:
                    tr.memory_leak = True 
            
            if child_process.returncode != 0 and \
               child_process.returncode not in self.reserved_exit_codes:
                """
                A step in the toolchain has returned a non-zero exit status. If "allowError"
                is specified in the config, we can perform a lenient diff based on CompileTime
                or RuntimeError message rules. Otherwise, we abort the toolchain.
                """
                tr.gen_output=step_stderr
                tr.failing_step=step.name
                tr.error_test=True

                # fail by default if errors are not explicitly allowed in config
                if not step.allow_error:
                    tr.did_pass = False

                # get compile time error result is not last step
                elif step.allow_error:
                    # TODO: Adjust SizeError and MathError definitions
                    # so we don't need to handle them specially.
                    if "SizeError" in str(expected):
                        error_pattern = r'\s*(SizeError):?.*'
                    elif "MathError" in str(expected):
                        error_pattern = r'\s*(MathError):?.*'
                    elif not last_step:
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
                    step_stdout = file_to_bytes(output_file) or b''
                  
                tr.time=step_time
                tr.gen_output=step_stdout

                # Diff the produced and expected outputs
                diff = precise_diff(step_stdout, expected)
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
        
        # this code should be unreachable for well-defined toolchains 
        raise RuntimeError("Toolchain reached undefined conditions during execution.")

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
        cmd.args = resolved 
        return cmd

    @staticmethod
    def replace_magic_args(command: Command, params: MagicParams) -> Command: 
        """
        Magic args are inherited from previous steps
        """
        resolved = []
        for arg in command.args:
            if '$EXE' in arg:
                resolved.append(arg.replace('$EXE', params.exe_path))
            elif '$INPUT' in arg and params.input_file:
                resolved.append(arg.replace('$INPUT', params.input_file))
            elif '$OUTPUT' in arg and params.output_file:
                resolved.append(arg.replace('$OUTPUT', params.output_file))
            else:
                resolved.append(arg)
        command.args = resolved
        command.cmd = command.args[0]
        return command

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
    if not produced or not expected:
        return "[ERROR] Test failed to generate bytes"

    produced_first_line = produced.split(b'\n', 1)[0]
    produced_str = p.strip() if (p := bytes_to_str(produced_first_line)) else None
    expected_str = e.strip() if (e := bytes_to_str(expected)) else None

    if not produced_str or not expected_str:
        return "[ERROR] Failed to decode error bytes"

    # Apply the mask/filter to both strings
    produced_masked = re.sub(pattern, r'\1', produced_str, flags=re.IGNORECASE | re.DOTALL)
    expected_masked = re.sub(pattern, r'\1', expected_str, flags=re.IGNORECASE | re.DOTALL)
       
    # If the masked strings are identical, return an empty string (no diff)
    if produced_masked.lower() == expected_masked.lower(): 
        return ""

    return diff_bytes(produced, expected)

