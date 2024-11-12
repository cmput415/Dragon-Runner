import os
import subprocess
import shutil
import argparse
from pathlib import Path

def build(build_path:str, log_path: str, n_threads: str): 
    """
    Entry point for dragon-runner to run the script.
    """ 
    print("[RUNNING] build script")

    directories = [d for d in Path(build_path).iterdir() if d.is_dir() and d.name != '.'] 
    for dir_path in directories:
        print(f"-- Building project: {dir_path.name}")
        
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
            subprocess.run(['cmake', '..'], check=True)
            subprocess.run(['make', '-j', n_threads], check=True)
        except subprocess.CalledProcessError:
            with open(log_path, 'a') as f:
                f.write(f"{dir_path.name}: build failed\n")
        finally:
            os.chdir(build_path)
    
    print(f"Build process completed. Check {log_path} for any failed builds.")

if __name__ == '__main__':
    
    """
    An entry point to run the script manually
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("build_path", type=Path, help="Path to build directory")
    parser.add_argument("log_file", type=Path, help="Path to error log file")
    args = parser.parse_args()
    
    args.error_file.unlink(missing_ok=True)

    build(args.build_path, args.log_file)
