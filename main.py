import subprocess
import os
import sys
from typing import List, Dict
from config import load_config, gather_tests, TestConfig
from cli import parse_cli_args

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

def run_toolchain(toolchain: List[Dict], test_file: str, config: Dict) -> None:
    
    print("Running toolchain: ")

    exe_path = config['tested_executable_paths']['solution']
    runtime_path = config['runtimes']['solution']
    
    input_file = test_file
    for step in toolchain:
        output_file = step['output'] if step['output'] != '-' else None
        
        try:
            result = run_step(step, input_file, output_file, runtime_path, exe_path)
            
            if result.returncode != 0:
                print(f"Error in step {step['stepName']} for test {test_file}")
                print(f"Command: {' '.join(result.args)}")
                print(f"Return code: {result.returncode}")
                print(f"Stderr: {result.stderr}")
                if step["allowError"]:
                    print("Terminating toolchain early") 
                    break
                else:
                    exit(1)

            if step['output'] == '-':
                print(f"Output for {test_file}:")
                print(result.stdout)
            
            input_file = output_file
        except Exception as e:
            print(f"Exception in step {step['stepName']} for test {test_file}: {str(e)}")
            return

def main():
    args = parse_cli_args()
    config = load_config(args.config_file)
    tests = gather_tests(config.test_dir)

    toolchain = config.toolchains['gazprea-llc']

    for test in tests:
        print(f"Running test: {test}")
        run_toolchain(toolchain, os.path.join(config.test_dir, test), config.to_dict())

if __name__ == "__main__":
    main()
