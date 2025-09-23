"""
============================== 415 Grading Script ==============================
Author: Justin Meimar 
Name: gen_config.py
Desc: 
================================================================================
"""
import json
import argparse
from typing import Optional
from pathlib import Path
from .key import Key

def gen_config(key_path:Path,
               submission_dir:Path,
               binary:str,
               runtime:Optional[str]=None): 
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
        
    executables_config = {}
    runtimes_config = {}
    config = {}
        
    assert key_path.is_file(), "must supply regular file as key" 
    assert submission_dir.is_dir(), "must supply directory to submissions."
        
    key = Key(key_path)
    for (sids, repo_suffix) in key.iter_both():
        match_dir = [d for d in submission_dir.iterdir() if d.is_dir() and str(repo_suffix) in d.name]
        if match_dir == []:
            print(f"Couldn't find: repo with suffix {repo_suffix}")
            exit(1)

        match_dir = Path(match_dir[0])
        expected_package = match_dir / "tests/testfiles" / sids 
        expected_binary = match_dir / f"bin/{binary}"
        expected_runtime = match_dir / f"bin/{runtime}"
        
        if not expected_package.is_file:
            print(f"Can not find expected package: {expected_package}")
            break;
        
        if not expected_binary.is_file:
            print(f"Can not find expected binary: {expected_binary}")
            break;
        
        if runtime is not None and not expected_runtime.is_file:
            print(f"Can not find expected binary: {expected_binary}")
            break;    
        
        executables_config.update({f"{sids}":f"{Path.absolute(expected_binary)}"})
        runtimes_config.update({f"{sids}":f"{Path.absolute(expected_runtime)}"})     
    
    config.update({"testedExecutablePaths": executables_config})
    if runtime is not None:
        config.update({"runtimes": runtimes_config})

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
        parser.add_argument("--runtime", type=str, default=None,
            help="Name of runtime library to expect in prohjects bin/")
        
        args = parser.parse_args()  
        gen_config(args.key_path, args.submissions_path, args.binary, args.runtime)
    
    else:
        # use the args provided by dragon-runner loader.py
        gen_config(*args)

if __name__ == '__main__':
   main() 
 
