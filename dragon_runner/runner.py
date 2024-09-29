import subprocess
import os
import re
import io

from io                         import BytesIO
from typing                     import List, Dict, Optional
from dataclasses                import dataclass
from difflib                    import Differ
from colorama                   import Fore, init
from dragon_runner.testfile     import TestFile 
from dragon_runner.config       import Executable, ToolChain
from dragon_runner.log          import log
from dragon_runner.utils        import make_tmp_file, bytes_to_str
from dragon_runner.toolchain    import Step

init(autoreset=True)

@dataclass
class ToolChainResult:
    success: bool
    stdout: BytesIO 
    stderr: BytesIO
    exit_code: int
    last_command: List[str] = [],
    last_step: Step={},
    time: Optional[float] = 0

@dataclass
class TestResult:
    did_pass: bool
    error_test: bool
    diff: Optional[str] = None

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

def run_command(command: List[str],
                input_stream: Optional[io.BytesIO],
                env: Dict[str, str] = {}) -> subprocess.CompletedProcess: 
    env = os.environ.copy() 
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE 
    
    input_bytes = input_stream.getvalue() if input_stream is not None else None
    return subprocess.run(command, env=env, input=input_bytes, stdout=stdout, stderr=stderr, check=False)

def run_toolchain(test: TestFile, toolchain: ToolChain, exe: Executable) -> ToolChainResult:
    log(f"Running test: {test.stem} ToolChain: {toolchain.name} Binary: {exe.id}", level=1)
   
    input_file = test.test_path
    current_dir = os.getcwd() 
    test.get_input_stream()

    for step in toolchain: 
        output_file = os.path.join(current_dir, step.output) if step.output else None
        input_stream = test.get_input_stream() if step.uses_ins else None
        command = [step.exe_path] + step.arguments
        command = replace_magic_args(command, exe.exe_path, input_file, output_file)
        command = replace_env_vars(command)
        
        # Wrap the command with os.path.abspath if it's not an absolute path
        if not os.path.isabs(command[0]):
            command[0] = os.path.abspath(os.path.join(current_dir, command[0]))
        
        log("Command: ", command, level=2)
        if input_stream is not None:
            log("Input stream:", input_stream.getvalue(), level=2)
        
        result = run_command(command, input_stream) 
        log("Result exit code: ", result.returncode, level=2)
        log("Result stdout:", result.stdout, level=2)
        log("Result stderr:", result.stderr, level=2)
        log("Test expected out:", bytes_to_str(test.get_expected_out()), level=2)
        
        if result.returncode != 0 and not step.allow_error:
            log("Aborting toolchain early", level=1)
            return ToolChainResult(
                success=False,
                stdout=io.BytesIO(result.stdout),
                stderr=io.BytesIO(result.stderr),
                exit_code=result.returncode,
                last_command=command,
                last_step=step
            )
        
        input_file = output_file if step.output else make_tmp_file(io.BytesIO(result.stdout))
 
    return ToolChainResult(
        success=True,
        stdout=io.BytesIO(result.stdout),
        stderr=io.BytesIO(result.stderr),
        exit_code=result.returncode,
        last_command=command,
        last_step=step
    )

def get_test_result(tool_chain_result: ToolChainResult, expected_out: BytesIO) -> TestResult:
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

    if tool_chain_result.success:
        if tool_chain_result.exit_code == 0:
            # Regular test: Take precise diff from only stdout
            diff = precise_diff(tool_chain_result.stdout, expected_out)
            if not diff: 
                return TestResult(did_pass=True, error_test=False)
            else:
                return TestResult(did_pass=False, error_test=False, )
        else:
            # Error Test: Take lenient diff from only stderr 
            ct_diff = lenient_diff(tool_chain_result.stderr, expected_out, compile_time_pattern)
            rt_diff = lenient_diff(tool_chain_result.stderr, expected_out, runtime_pattern)
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