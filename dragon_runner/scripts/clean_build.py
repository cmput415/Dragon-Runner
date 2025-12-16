import sys
import shutil
from pathlib import Path
import argparse
from typing import List
from dragon_runner.scripts.base import Script


class CleanBuildScript(Script):

    @classmethod
    def name(cls) -> str:
        return "clean-build"

    @classmethod
    def description(cls) -> str:
        return "Remove build directories from student submissions"

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="clean-build",
            description="Remove build directories from all submissions"
        )
        parser.add_argument('submission_dir', type=Path, help='Directory of submissions to clean')
        return parser

    @staticmethod
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

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)

        sub = Path(parsed_args.submission_dir)

        if not sub.exists():
            print("Submission directory does not exist...")
            return 1

        cls.remove_build_dirs(sub)
        return 0

if __name__ == "__main__":
    sys.exit(CleanBuildScript.main(sys.argv[1:]))

