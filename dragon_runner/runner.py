import subprocess
import os
import re
import io

from io                     import BytesIO
from typing                 import List, Dict, Optional
from dataclasses            import dataclass
from difflib                import Differ
from colorama               import Fore, init
from dragon_runner.testfile import TestFile 
from dragon_runner.config   import Executable, ToolChain
from dragon_runner.log      import log

init(autoreset=True)

@dataclass
class ToolChainResult:
    success: bool
    stdout: BytesIO 
    stderr: BytesIO
    exit_code: int
    time: Optional[float] = 0
    exeption: Optional[Exception] = None

@dataclass
class TestResult:
    did_pass: bool
    did_error: bool
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
        
        # TODO: how to handle when step has no output
        output_file = os.path.join(current_dir, step.output) if step.output else input_file
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
        
        if result.returncode != 0 and not step.allow_error:
            log("Aborting toolchain early")
            return ToolChainResult(
                success=False,
                stdout=io.BytesIO(result.stdout),
                stderr=io.BytesIO(result.stderr),
                exit_code=result.returncode
            )
        
        input_file = output_file
 
    return ToolChainResult(
        success=True,
        stdout=io.BytesIO(result.stdout),
        stderr=io.BytesIO(result.stderr),
        exit_code=result.returncode
    )

def get_test_result(tool_chain_result: ToolChainResult, expected_out: BytesIO) -> TestResult:
    """
    Determine the test result based on ToolChainResult and expected output.

    Rules:
    1) If success is True, then stdout and expected_out match precisely and stderr is empty
       -> TestResult(did_pass=True, did_error=False)
    2) If success is False, then stderr and expected_out match leniently and stdout is empty
       -> TestResult(did_pass=True, did_error=True)
    3) If success is False and rule 2 is not met
       -> TestResult(did_pass=False, did_error=True, diff)
    4) If success is True and rule 1 is not met
       -> TestResult(did_pass=False, did_error=False, diff)
    """
    if tool_chain_result.success:
        if tool_chain_result.stderr.getvalue() == b'' and precise_diff(tool_chain_result.stdout, expected_out) == "":
            return TestResult(did_pass=True, did_error=False)
        else:
            diff = precise_diff(tool_chain_result.stdout, expected_out)
            return TestResult(did_pass=False, did_error=False, diff=diff)
    else:
        if tool_chain_result.stdout.getvalue() == b'' and lenient_diff(tool_chain_result.stderr, expected_out) == "":
            return TestResult(did_pass=True, did_error=True)
        else:
            diff = lenient_diff(tool_chain_result.stderr, expected_out)
            return TestResult(did_pass=False, did_error=True, diff=diff)

def precise_diff(produced: BytesIO, expected: BytesIO) -> str:
    """
    Return the difference of two byte strings, otherwise empty string 
    """
    produced_str = produced.getvalue().decode('utf-8')
    expected_str = expected.getvalue().decode('utf-8')

    # if the strings are exactly the same produce no diff
    if produced_str == expected_str:
        return ""

    differ = Differ()
    diff = list(differ.compare(produced_str.splitlines(), expected_str.splitlines()))

    return color_diff(diff)

def lenient_diff(produced: BytesIO, expected: BytesIO, pattern: str = r'\S+') -> str:
    """
    Check if the produced bytes are different from the expected bytes with
    respect to the regex pattern.
    """
    produced_str = produced.getvalue().decode('utf-8')
    expected_str = expected.getvalue().decode('utf-8')

    # Replace pattern matches with a placeholder in both strings
    produced_normalized = re.sub(pattern, '***', produced_str)
    expected_normalized = re.sub(pattern, '***', expected_str)

    differ = Differ()
    diff = list(differ.compare(produced_normalized.splitlines(), expected_normalized.splitlines()))

    return color_diff(diff) if diff else ""

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