import subprocess
import os
import re

from typing import List, Dict, Tuple
from test import Test 
from config import Executable, ToolChain, Config
from toolchain import Step

def replace_env_vars(args: List[str]) -> List[str]:
    """
    Expand environment variables, enclosed in ${VAR} with the current shells value
    """
    resolved = []
    for arg in args:
        matches = re.findall(r'\$(\w+)|\$\{(\w+)\}', arg)
        if matches:
            for match in matches:
                var_name = match[0] or match[1]
                env_value = os.environ.get(var_name)
                if env_value is None:
                    raise Exception(f"Failed to source env var: ${var_name} from {arg}")
                arg = arg.replace(f"${var_name}", env_value).replace(f"${{{var_name}}}", env_value)
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

def run_toolchain(test: Test, toolchain: ToolChain, exe: Executable):

    print(f"Running test: {test.stem} ToolChain: {toolchain.name} Binary: {exe.id}")
   
    input_file = test.test_path # to start the test is the initial input 
    output_file = "/dev/null"

    for step in toolchain: 
        if step.output:
            output_file = os.path.join('./', step.output)
        
        command = [step.command] + step.arguments
        command = replace_magic_args(command, exe.binary, input_file, output_file)
        command = replace_env_vars(command)
         
        result = run_command(command, step.uses_ins, step.output)
        
        if step.output:
            input_file = step.output

def run_command(command : List[str],
                uses_ins: bool=False,
                last_step: bool=False, 
                env: Dict[str, str]={}) -> subprocess.CompletedProcess:
    
    print("-- Running: ", '\n'.join(command))
   
    env = os.environ.copy()
 
    stdin = subprocess.PIPE if uses_ins else None
    stdout = subprocess.PIPE if last_step else subprocess.DEVNULL
    stderr = subprocess.PIPE if last_step else subprocess.DEVNULL

    return subprocess.run(command, env=env, stdin=stdin, stdout=stdout, stderr=stderr, text=True) 
