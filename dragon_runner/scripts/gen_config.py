import json
import argparse
from typing import Optional
from pathlib import Path

def gen_config(
        key_str:str,
        submission_dir_str:str,
        binary:str,
        runtime:Optional[str]=None
    ): 
    """
    @key: a text file containing all the ccid/team names expected to be collected 
    @submission_dir: the directory of cloned student repos
    @binary: the expected binary name
    @runtime: the expected runtime name (optional)

    description: For each ccid/team in @key file, traverse the @submission_dir looking
        for a repository named with the key as the suffix. For example, a key of team-fun
        looks for gazprea-team-fun.

        Once the directory has been found, assert the following exist then copy into a json
        config: binary path, runtime_path.
    """
        
    key_path = Path(key_str)
    submission_dir_path = Path(submission_dir_str)
    
    executables_config = {}
    runtimes_config = {}
    config = {}
        
    assert key_path.is_file(), "must supply regular file as key" 
    assert submission_dir_path.is_dir(), "must supply directory to submissions."
     
    keys = Path(key_path).read_text().splitlines()  
    for key in keys:
        for dir in Path.iterdir(submission_dir_path):
            if key in str(dir):

                # look for the expected test package, binary and (runtime)?
                expected_package = dir / "tests/testfiles" / key 
                expected_binary = dir / f"bin/{binary}"
                expected_runtime = dir / f"bin/{runtime}"

                if not expected_package.is_file:
                    print(f"Can not find expected package: {expected_package}")
                    break;
                
                if not expected_binary.is_file:
                    print(f"Can not find expected binary: {expected_binary}")
                    break;
                
                if runtime is not None and not expected_runtime.is_file:
                    print(f"Can not find expected binary: {expected_binary}")
                    break;
                
                executables_config.update({f"{key}":f"{Path.absolute(expected_binary)}"})
                runtimes_config.update({f"{key}":f"{Path.absolute(expected_runtime)}"})
    
    config = {
        "testedExecutablePaths": executables_config,
        "runtimes": runtimes_config
    }
    
    # print to terminal and save 
    print(json.dumps(config, indent=4))
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

def main(*args):
    if not args:
        # let script be used directly from commandline, without dragon-runner
        parser = argparse.ArgumentParser() 
        parser.add_argument("key_path", type=Path,
            help="Path to key file containing each team/ccid on a line.")
        parser.add_argument("submissions_path", type=Path,
            help="Path to project submissions cloned from github classroom.")
        parser.add_argument("binary", type=str,
            help="Name of binary to expect in prohjects bin/")
        parser.add_argument("runtime", type=str,
            help="Name of runtime library to expect in prohjects bin/")
        
        args = parser.parse_args()  
        gen_config(args.key_path, args.submissions_path, args.binary, args.runtime)
    
    else:
        # use the args provided by dragon-runner loader.py
        gen_config(*args)

if __name__ == '__main__':
   main() 
 
