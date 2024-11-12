import os
import subprocess
import shutil
import argparse
from pathlib import Path

def build(build_path: str, log_path: str, n_threads: str="2"): 
    directories = [d for d in Path(build_path).iterdir() if d.is_dir() and d.name != '.'] 
    
    for dir_path in directories:
        print(f"-- Building project: {dir_path.name}", end='')
        
        try:
            os.chdir(dir_path)
        except OSError:
            with open(log_path, 'a') as f:
                f.write(f"{dir_path.name}: Failed to change directory\n")
            continue
            
        if (dir_path / 'build').exists():
            shutil.rmtree('build')
        
        os.makedirs('build')
        os.chdir('build')
        
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
            os.chdir(build_path)
    
    print(f"Build process completed. Check {log_path} for build output and errors.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("build_path", type=Path, help="Path to build directory")
    parser.add_argument("log_file", type=Path, help="Path to log file")
    
    args = parser.parse_args()
    args.log_file.unlink(missing_ok=True)
    
    build(args.build_path, args.log_file)
