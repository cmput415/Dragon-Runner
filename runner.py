import subprocess
import os
from typing import List, Dict, Tuple
from test import Test 
from config import Executable, ToolChain, Config
from toolchain import Step

def run_toolchain(test: Test, toolchain: ToolChain, exe: Executable):
    
    print(f"Running test: {test.stem} ToolChain: {toolchain.name} Binary: {exe.id}") 
    for step in toolchain:
        
        result = run_step(step)

    """
    
       output_file = step['output'] if step['output'] != '-' else None
        
        try:
            result = run_step(step, test_src)
            
            if result.returncode != 0:
                print(f"Error in step {step['stepName']} for test {input_file}")
                print(f"Command: {' '.join(result.args)}")
                print(f"Return code: {result.returncode}")
                print(f"Stderr: {result.stderr}")
                if step["allowError"]:
                    print("Terminating toolchain early")
                    break
                else:
                    exit(1)
            
            if step['output'] == '-':
                print(f"Output for {input_file}:{result.stdout}")
                print(f"Expected out for {input_file}:{read_file(test_triple[1])}")
                
                if result.stdout == read_file(test_triple[1]):
                    print("===== PASS")
                else:
                    print("===== FAIL")
            
            # prepare next input
            input_file = output_file

        except Exception as e:
            print(f"Exception in step {step['stepName']} for test {input_file}: {str(e)}")
            return
    """
    
def run_step(step: Step):
    print("Running Step: ", step.name)
    
    full_command = [step.command, step.arguments]

    """
def run_step(step: Dict, input_file: str, output_file: str, runtime_path: str, exe_path: str) -> subprocess.CompletedProcess:
    command = [step['executablePath']]
    for arg in step['arguments']:
        if arg == '$INPUT':
            command.append(input_file)
        elif arg == '$OUTPUT':
            command.append(output_file)
        elif arg == '-L$RT_PATH':
            command.append(f'-L{os.path.dirname(runtime_path)}')
        elif arg == '-l$RT_LIB':
            command.append(f'-l{os.path.splitext(os.path.basename(runtime_path))[0][3:]}')
        else:
            command.append(arg)
    
    step_exe_path = step['executablePath']
    if step_exe_path == "$EXE":
        command[0] = exe_path
    elif step_exe_path == "$INPUT":
        command[0] = "./" + input_file
    else:
        command[0] = step['executablePath']

    env = os.environ.copy()
    if step['usesRuntime']:
        env['LD_LIBRARY_PATH'] = os.path.dirname(runtime_path)

    print("COMMAND: ", command)
    
    stdin = subprocess.PIPE if step['usesInStr'] else None
    stdout = subprocess.PIPE if step['output'] == '-' else subprocess.DEVNULL
    stderr = subprocess.PIPE

    return subprocess.run(command, env=env, stdin=stdin, stdout=stdout, stderr=stderr, text=True)
    """

