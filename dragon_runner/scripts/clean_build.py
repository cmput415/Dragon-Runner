import sys
import shutil
from pathlib import Path
import argparse

def remove_build_dirs(submissions_dir: Path):
    for submission_dir in sorted(submissions_dir.iterdir()):
        if not submission_dir.is_dir():
            continue
        
        build_dir = submission_dir / 'build'
        if not build_dir.exists():
            continue
            
        print(f"Removing build directory in: {submission_dir.name}")
        try:
            shutil.rmtree(build_dir)
            print(f"  Successfully removed")
        except Exception as e:
            print(f"  Failed: {e}")

def clean_build():
    parser = argparse.ArgumentParser()
    parser.add_argument('submission_dir')
    args = parser.parse_args()
    
    sub = Path(args.submission_dir)
    
    if not sub.exists():
        print("Submission directory does not exist...")
        sys.exit(1)
    
    remove_build_dirs(sub)

if __name__ == "__main__":
    clean_build()

