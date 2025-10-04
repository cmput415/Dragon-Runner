import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

def get_commit_at_time(repo_path, checkout_time):
    result = subprocess.run(
        ['git', 'rev-list', '-1', f'--before={checkout_time}', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()

def get_commit_time(repo_path, commit_hash):
    result = subprocess.run(
        ['git', 'show', '-s', '--format=%ci', commit_hash],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()

def checkout_commit(repo_path, commit_hash):
    result = subprocess.run(
        ['git', 'checkout', commit_hash],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def process_repositories(submissions_dir: Path, checkout_time: str):
    for submission_dir in sorted(submissions_dir.iterdir()):
        if not submission_dir.is_dir():
            continue
        
        git_dir = submission_dir / '.git'
        if not git_dir.exists():
            print(f"\nSkipping {submission_dir.name} - not a git repository")
            continue 
        print(f"\nProcessing: {submission_dir.name}")
        
        commit_hash = get_commit_at_time(submission_dir, checkout_time) 
        if not commit_hash:
            print(f"  No commits found before {checkout_time}")
            continue
        
        commit_time = get_commit_time(submission_dir, commit_hash) 
        if checkout_commit(submission_dir, commit_hash):
            print(f"  Checked out to: {commit_hash[:8]}")
            print(f"  Commit time: {commit_time}")
        else:
            print(f"  Failed to checkout {commit_hash[:8]}")

def validate_checkout_time(time_str):
    try:
        datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        return True
    except ValueError:
        return False

def checkout():
    parser = argparse.ArgumentParser()
    parser.add_argument('submission_dir')
    parser.add_argument('checkout_time', help='Format: "YYYY-MM-DD HH:MM:SS"')
    args = parser.parse_args()
    
    sub = Path(args.submission_dir)
    
    if not sub.exists():
        print("Submission directory does not exist...")
        sys.exit(1)
    
    if not validate_checkout_time(args.checkout_time):
        print('Invalid checkout_time format. Use: "YYYY-MM-DD HH:MM:SS"')
        sys.exit(1)
    
    print(f"Using submission dir: {sub}")
    print(f"Checking out to latest commit before: {args.checkout_time}")
    
    process_repositories(sub, args.checkout_time)

if __name__ == "__main__":
    checkout()

