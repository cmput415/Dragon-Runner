"""
============================== 415 Grading Script ==============================
Author: Justin Meimar
Name: gather.py
Desc:
================================================================================
"""

import sys
import shutil
import argparse
from pathlib import Path
from typing import List
from base import Script
from key import Key


class GatherScript(Script):

    @classmethod
    def name(cls) -> str:
        return "gather"

    @classmethod
    def description(cls) -> str:
        return "Gather test files from student submissions"

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="gather",
            description="Gather all the testfiles in student directories"
        )
        parser.add_argument("key_file", type=Path, help="Path to CSV key file")
        parser.add_argument("search_path", type=Path, help="Path to search for test files")
        parser.add_argument("--assignment", type=str, required=True,
            help="Assignment column name from key file (e.g. A1)")
        return parser

    @staticmethod
    def gather(key_file: Path,
           search_path: Path,
           assignment: str,
           output_dir: str = "submitted-testfiles"):

        key = Key(key_file)
        search_dir = Path(search_path)

        if not search_dir.is_dir():
            print("Could not find search directory.")
            return 1

        directories = [d for d in search_dir.iterdir() if d.is_dir()]
        for rec in key.iter_students():
            repo = rec.repos.get(assignment)
            if not repo:
                print(f"No repo for {rec.sid} in assignment {assignment}, skipping")
                continue

            print(f"Finding submission for: {rec.ccid} (repo: {repo})")
            for d in directories:
                if repo in d.name:
                    expected_test_dir = d / "tests" / "testfiles" / rec.sid

                    if expected_test_dir.is_dir():
                        print(f"-- Found properly formatted testfiles for {rec.sid}")
                        shutil.copytree(expected_test_dir, (Path(output_dir) / rec.sid), dirs_exist_ok=True)
                        break
                    else:
                        print(f"-- Could NOT find testfiles for {rec.sid}")
                        exit(1)

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)
        cls.gather(parsed_args.key_file, parsed_args.search_path, parsed_args.assignment)
        return 0

if __name__ == '__main__':
    sys.exit(GatherScript.main(sys.argv[1:]))
