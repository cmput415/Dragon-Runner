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
from dragon_runner.scripts.base import Script


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
        parser.add_argument("key_file", type=Path, help="Key file which has a line for each (SID, GH_Username) pair")
        parser.add_argument("search_path", type=Path, help="Path to search for test files")
        parser.add_argument("project_name", type=Path, help="Path to search for test files")
        return parser

    @staticmethod
    def load_key(key_path: Path):
        config = {}
        with open(key_path) as key_file:
            for line in key_file.readlines():
                sid, gh_username = line.strip().split(' ')
                print("SID: ", sid, "\tGH Username: ", gh_username)
                config[sid] = gh_username
        return config

    @staticmethod
    def gather(key_file: Path,
           search_path: str,
           project_name: str,
           output_dir: str = "submitted-testfiles"):
        is_rt = True
        config = GatherScript.load_key(key_file)
        search_dir = Path(search_path)
        project_name = str(project_name).strip()

        if not search_dir.is_dir():
            error = "Could not create test directory."
            print(error)
            return 1

        directories = [d for d in search_dir.iterdir() if d.is_dir() and str(project_name) in d.name]
        for (sid, gh_user) in config.items():
            print("Finding submission for: ", gh_user)
            for d in directories:
                if gh_user in str(d):
                    if is_rt:
                        suffix = '-'.join(gh_user.split('-')[1:])
                        expected_test_dir = d / "tests" / "testfiles" / suffix
                    else:
                        expected_test_dir = d / "tests" / "testfiles" / sid

                    if expected_test_dir.is_dir():
                        print(f"-- Found properly formatted testfiles for {sid}")
                        shutil.copytree(expected_test_dir, (Path(output_dir) / sid), dirs_exist_ok=True)
                        break
                    else:
                        print(f"-- Could NOT find testfiles for {sid}")
                        exit(1)

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)
        cls.gather(parsed_args.key_file, parsed_args.search_path, parsed_args.project_name)
        return 0

if __name__ == '__main__':
    sys.exit(GatherScript.main(sys.argv[1:]))

