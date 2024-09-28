import subprocess
import os
import re
import io

from io                     import BytesIO
from typing                 import List, Dict, Optional
from dataclasses            import dataclass
from dragon_runner.testfile import TestFile 
from dragon_runner.config   import Executable, ToolChain
from dragon_runner.log      import log

@dataclass
class ToolchainResult:
    success: bool
    stdout: BytesIO 
    stderr: BytesIO
    time: Optional[float] = 0
    exeption: Optional[Exception] = None

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
        if arg == "@EXE":
            resolved.append(binary)
        elif arg == '@INPUT':
            resolved.append(input_file)
        elif arg == '@OUTPUT':
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

def run_toolchain(test: TestFile, toolchain: ToolChain, exe: Executable) -> ToolchainResult:
    log(f"Running test: {test.stem} ToolChain: {toolchain.name} Binary: {exe.id}", level=1)
   
    input_file = test.test_path
    current_dir = os.getcwd()
    
    test.get_input_stream()
    for step in toolchain:
        
        # TODO: how to handle when step has no output
        output_file = os.path.join(current_dir, step.output) if step.output else input_file
        input_stream = test.get_input_stream() if step.uses_ins else None
        command = [step.command] + step.arguments
        command = replace_magic_args(command, exe.binary, input_file, output_file)
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
            return ToolchainResult(
                success=False,
                stdout=io.BytesIO(result.stdout),
                stderr=io.BytesIO(result.stderr),
            )
        
        input_file = output_file
 
    return ToolchainResult(
        success=True,
        stdout=io.BytesIO(result.stdout),
        stderr=io.BytesIO(result.stderr)
    )

