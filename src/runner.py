import subprocess
import os
import re

from utils import dump_file
from typing import List, Dict, Optional
from test import Test 
from config import Executable, ToolChain
from dataclasses import dataclass
from log import log

@dataclass
class ToolchainResult:
    success: bool
    stdout: str
    stderr: str
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

def run_toolchain(test: Test, toolchain: ToolChain, exe: Executable) -> ToolchainResult:
    log(f"Running test: {test.stem} ToolChain: {toolchain.name} Binary: {exe.id}", level=1)
   
    input_file = test.test_path
    current_dir = os.getcwd()
    
    test.get_input_stream()
    for step in toolchain:
        if step.output:
            output_file = os.path.join(current_dir, step.output)
        else:
            output_file = input_file
        
        input_stream = test.get_input_stream() if step.uses_ins else None
        
        command = [step.command] + step.arguments
        command = replace_magic_args(command, exe.binary, input_file, output_file)
        command = replace_env_vars(command)
        
        # Wrap the command with os.path.abspath if it's not an absolute path
        if not os.path.isabs(command[0]):
            command[0] = os.path.abspath(os.path.join(current_dir, command[0]))
        
        result = run_command(command, input_stream)
         
        log("Command: ", command, level=2)
        log("Result exit code: ", result.returncode, level=2)
        log("Result stdout:", result.stdout, level=2)
        log("Result stderr:", result.stderr, level=2)
        
        if result.returncode != 0 and not step.allow_error:
            log("Aborting toolchain early")
            return ToolchainResult(
                success=False,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        
        input_file = output_file
 
    return ToolchainResult(
        success=True,
        stdout=result.stdout,
        stderr=result.stderr
    )

def run_command(command: List[str],
                input_stream: Optional[str],
                env: Dict[str, str] = {}) -> subprocess.CompletedProcess:
      
    env = os.environ.copy() 
    stdin = subprocess.PIPE if input_stream else None
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE 

    return subprocess.run(command, env=env, stdin=stdin, stdout=stdout, stderr=stderr, text=True)


