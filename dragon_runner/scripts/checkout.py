import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import List
from dragon_runner.scripts.base import Script


class CheckoutScript(Script):

    @classmethod
    def name(cls) -> str:
        return "checkout"

    @classmethod
    def description(cls) -> str:
        return "Checkout git repositories to the latest commit before a specified time"

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="checkout",
            description="Checkout student git repositories to a specific commit time"
        )
        parser.add_argument('submission_dir',
                          type=Path,
                          help='Directory of repositories to checkout')
        parser.add_argument('checkout_time',
                          help='Checkout time in format: "YYYY-MM-DD HH:MM:SS"')
        return parser

    @classmethod
    def get_commit_at_time(cls, repo_path, checkout_time):
        result = subprocess.run(
            ['git', 'rev-list', '-1', f'--before={checkout_time}', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    @classmethod
    def get_commit_time(cls, repo_path, commit_hash):
        result = subprocess.run(
            ['git', 'show', '-s', '--format=%ci', commit_hash],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    @classmethod
    def checkout_commit(cls, repo_path, commit_hash):
        result = subprocess.run(
            ['git', 'checkout', commit_hash],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0

    @classmethod
    def process_repositories(cls, submissions_dir: Path, checkout_time: str):
        for submission_dir in sorted(submissions_dir.iterdir()):
            if not submission_dir.is_dir():
                continue

            git_dir = submission_dir / '.git'
            if not git_dir.exists():
                print(f"\nSkipping {submission_dir.name} - not a git repository")
                continue
            print(f"\nProcessing: {submission_dir.name}")

            commit_hash = cls.get_commit_at_time(submission_dir, checkout_time)
            if not commit_hash:
                print(f"  No commits found before {checkout_time}")
                continue

            commit_time = cls.get_commit_time(submission_dir, commit_hash)
            if cls.checkout_commit(submission_dir, commit_hash):
                print(f"  Checked out to: {commit_hash[:8]}")
                print(f"  Commit time: {commit_time}")
            else:
                print(f"  Failed to checkout {commit_hash[:8]}")

    @classmethod
    def validate_checkout_time(cls, time_str):
        try:
            datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            return True
        except ValueError:
            return False

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)

        sub = Path(parsed_args.submission_dir)

        if not sub.exists():
            print("Submission directory does not exist...")
            return 1

        if not cls.validate_checkout_time(parsed_args.checkout_time):
            print('Invalid checkout_time format. Use: "YYYY-MM-DD HH:MM:SS"')
            return 1

        print(f"Using submission dir: {sub}")
        print(f"Checking out to latest commit before: {parsed_args.checkout_time}")

        cls.process_repositories(sub, parsed_args.checkout_time)
        return 0

if __name__ == "__main__":
    sys.exit(CheckoutScript.main(sys.argv[1:]))

