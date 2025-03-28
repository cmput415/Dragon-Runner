"""
============================== 415 Grading Script ==============================
Author: Justin Meimar 
Name: build.py
Desc: build the compilers with cmake.. && make -j <n> and log those which
      fail.
================================================================================
"""

import os
import subprocess
import shutil
import argparse
from pathlib import Path

def build(build_path, log_path, n_threads="2"): 
    root_path = Path(build_path).absolute()
    log_path = Path(log_path).absolute()

    directories = [d for d in root_path.iterdir() if d.is_dir() and d.name != '.'] 
    
    print("Directories to build:")
    for d in directories:
        print(" ", d)

    for dir_path in directories:
        print(f"-- Building project: {dir_path.name}", end='')
        
        build_dir_path = dir_path / 'build'
        
        try:
            os.chdir(dir_path)
        except OSError:
            with open(log_path, 'a') as f:
                f.write(f"{dir_path.name}: Failed to change directory\n")
            continue
           
        # remove and recreate build if it exists and change into it 
        if (build_dir_path).exists():
            shutil.rmtree(build_dir_path) 
        os.makedirs(build_dir_path)
        os.chdir(build_dir_path)
         
        try:
            with open(log_path, 'a') as log_file:
                log_file.write(f"\n=== Building {dir_path.name} ===\n")
                subprocess.run(
                    ['cmake', '..'],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=True
                )
                subprocess.run(
                    ['make', '-j', n_threads],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=True
                )
            print(" [SUCCESS]")
        except subprocess.CalledProcessError:
            print(f" [FAILED]")
            with open(log_path, 'a') as f:
                f.write(f"{dir_path.name}: build failed\n")
        finally:
            os.chdir(root_path)
    
    print(f"Build process completed. Check {log_path} for build output and errors.")

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("build_path", type=Path, help="Path to build directory")
    parser.add_argument("log_file", type=Path, help="Path to log file")
    parser.add_argument("n", type=int, default=2, help="n_threads")
    
    args = parser.parse_args()
    args.log_file.unlink(missing_ok=True)
    
    build(args.build_path, args.log_file, str(args.n))

