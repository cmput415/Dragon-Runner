"""
============================== 415 Grading Script ==============================
Author: Justin Meimar
Name: gen_config.py
Desc:
================================================================================
"""
import sys
import json
import argparse
from typing import Optional, List
from pathlib import Path
from base import Script
from key import Key


class GenConfigScript(Script):

    @classmethod
    def name(cls) -> str:
        return "gen-config"

    @classmethod
    def description(cls) -> str:
        return "Generate dragon-runner configuration from submissions"

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="gen-config",
            description="Generate dragon-runner configuration from student submissions"
        )
        parser.add_argument("key_path", type=Path,
            help="Path to CSV key file")
        parser.add_argument("submissions_path", type=Path,
            help="Path to project submissions cloned from github classroom.")
        parser.add_argument("binary", type=str,
            help="Name of binary to expect in projects bin/")
        parser.add_argument("--assignment", type=str, required=True,
            help="Assignment column name from key file (e.g. A1)")
        parser.add_argument("--runtime", type=str, default=None,
            help="Name of runtime library to expect in projects bin/")
        return parser

    @staticmethod
    def gen_config(key_path: Path,
               submission_dir: Path,
               binary: str,
               assignment: str,
               runtime: Optional[str] = None):

        executables_config = {}
        runtimes_config = {}
        config = {}

        assert key_path.is_file(), "must supply regular file as key"
        assert submission_dir.is_dir(), "must supply directory to submissions."

        key = Key(key_path)
        for repo in key.iter_repos(assignment):
            match_dir = [d for d in submission_dir.iterdir() if d.is_dir() and repo in d.name]
            if not match_dir:
                print(f"Couldn't find: repo with name {repo}")
                exit(1)

            match_dir = Path(match_dir[0])
            members = key.students_for_repo(assignment, repo)
            sid_label = ",".join(rec.sid for rec in members)

            expected_package = match_dir / "tests/testfiles" / sid_label
            expected_binary = match_dir / f"bin/{binary}"
            expected_runtime = match_dir / f"bin/{runtime}"

            if not expected_package.is_file:
                print(f"Can not find expected package: {expected_package}")
                break

            if not expected_binary.is_file:
                print(f"Can not find expected binary: {expected_binary}")
                break

            if runtime is not None and not expected_runtime.is_file:
                print(f"Can not find expected runtime: {expected_runtime}")
                break

            executables_config[sid_label] = str(Path.absolute(expected_binary))
            runtimes_config[sid_label] = str(Path.absolute(expected_runtime))

        config["testedExecutablePaths"] = executables_config
        if runtime is not None:
            config["runtimes"] = runtimes_config

        print(json.dumps(config, indent=4))
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)
        cls.gen_config(parsed_args.key_path, parsed_args.submissions_path,
                       parsed_args.binary, parsed_args.assignment, parsed_args.runtime)
        return 0

if __name__ == '__main__':
    sys.exit(GenConfigScript.main(sys.argv[1:]))
