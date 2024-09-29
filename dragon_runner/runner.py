import subprocess
import os
import re
import io
import time
from subprocess                 import TimeoutExpired, CompletedProcess
from io                         import BytesIO
from typing                     import List, Dict, Optional
from dataclasses                import dataclass
from difflib                    import Differ
from colorama                   import Fore, init
from dragon_runner.testfile     import TestFile 
from dragon_runner.config       import Executable, ToolChain
from dragon_runner.log          import log, log_multiline
from dragon_runner.utils        import make_tmp_file, bytes_to_str, file_to_bytes
from dragon_runner.toolchain    import Step

init(autoreset=True)

@dataclass
class ToolChainResult:
    success: bool
    stdout: BytesIO 
    stderr: BytesIO
    exit_code: int
    last_command: List[str]=[],
    last_step: Step={},
    time: Optional[float]=0

@dataclass
class CommandResult:
    subps_result: Optional[CompletedProcess]
    time: float=0
    timed_out: bool=False 
    def __iter__(self):
        return iter((self.subps_result, self.time, self.timed_out))

@dataclass
class TestResult:
    did_pass: bool
    error_test: bool
    time: Optional[float]=0
    diff: Optional[str]=None

def replace_env_vars(args: List[str]) -> List[str]:
    """
    Expand environment variables with the values from current shell
    """   
    resolved = []
    for arg in args:
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
    return resolved

def replace_magic_args(args: List[str], binary: str, input_file: str, output_file: str) -> List[str]:
    """
    Magic args are inherited from previous steps
    """
    resolved = []
    for arg in args:
        if arg == "$EXE":
            resolved.append(binary)
        elif arg == '$INPUT':
            resolved.append(input_file)
        elif arg == '$OUTPUT':
            resolved.append(output_file) 
        else:
            resolved.append(arg)
    return resolved

def run_toolchain(test: TestFile, toolchain: ToolChain, exe: Executable, timeout: float) -> ToolChainResult:
    """
    Entry point for toolchain running. 
    """  
    input_file = test.test_path
    current_dir = os.getcwd()
    log("Test expected out", test.get_expected_out().getvalue(), level=2)
    
    for index, step in enumerate(toolchain):
        is_last_step = index == len(toolchain) - 1
        
        input_stream = test.get_input_stream() if step.uses_ins else None 
        
        command, output_file         = prepare_command(step, exe, input_file, current_dir)
        result, wall_time, timed_out = run_command(command, input_stream, timeout=timeout)

        # check timeout 
        if timed_out:
            log(Fore.YELLOW + f"Timed out at step: {step.name} after {timeout} seconds", level=0)
            return ToolChainResult(False, BytesIO(b''), BytesIO(b''), 1, command, step)

        # check result status
        log_step(step, command, input_stream, result, wall_time) 
        if result.returncode != 0:
            if not step.allow_error:
                log("Aborting toolchain early", level=1)
            return create_tc_result(step.allow_error, result, command, step, wall_time)
         
        if is_last_step: 
            if output_file:
                file_contents = file_to_bytes(output_file)
                return ToolChainResult(True, file_contents, b'', result.returncode, command, step, wall_time) 
            else:
                return create_tc_result(True, result, command, step, wall_time)
        else:
            input_file = output_file or make_tmp_file(BytesIO(result.stdout))
    
    # This line should never be reached, but it's good to have as a fallback
    return create_tc_result(True, result, command, step, wall_time)

def run_command(command: List[str],
                input_stream: Optional[io.BytesIO],
                env: Dict[str, str] = {},
                timeout: float = 2.0) -> CommandResult:
    """
    Fork and exec the command once it has been resolved and return the result 
    """  
    env = os.environ.copy()
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE
    input_bytes = input_stream.getvalue() if input_stream is not None else None

    start_time = time.time()
    try:
        result = subprocess.run(command, env=env, input=input_bytes, stdout=stdout,
                                stderr=stderr, check=False, timeout=timeout)
        wall_time = time.time() - start_time
        return CommandResult(subps_result=result, time=wall_time)
    except TimeoutExpired:
        return CommandResult(subps_result=None, time=0, timed_out=True)

def prepare_command(step, exe, input_file, current_dir):
    """
    Resolve arguments and environment variables for the current command.
    """ 
    output_file = os.path.join(current_dir, step.output) if step.output else None
    command = replace_magic_args([step.exe_path] + step.arguments,
                                  exe.exe_path, input_file, output_file)
    command = replace_env_vars(command)
    command[0] = os.path.abspath(command[0]) if not os.path.isabs(command[0]) else command[0]
    return command, output_file

def log_step(step: Step, command: List[str], input_stream: BytesIO, result, wall_time):
    """
    Report what happened for a single step in the toolchain
    """
    log('=' * 20 + f" Step: {step.name} " + '='*20)
    log_multiline("Command: [" + ',\n\t'.join(command) + "]", indent=2)

    if input_stream:
        log("Input stream:", input_stream.getvalue(), level=2, indent=2)
    log("Result exit code:", result.returncode, level=2, indent=2)
    log("Result stdout:", result.stdout, level=2, indent=2)
    log("Result stderr:", result.stderr, level=2, indent=2)
    log("Step execution time:", f"{wall_time:.3f} seconds", level=2, indent=2)

def create_tc_result(success: bool, result, command, step, wall_time) -> ToolChainResult:
    return ToolChainResult(
        success=success,
        stdout=BytesIO(result.stdout),
        stderr=BytesIO(result.stderr),
        exit_code=result.returncode,
        last_command=command,
        last_step=step,
        time=wall_time
    )

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