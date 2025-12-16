"""
============================== 415 Grading Script ==============================
Author: Justin Meimar
Name: grade_perf.py
Desc: Dragon-runner with a config pointing to the performance tests & an
      executable for each compiler to be tested, when run with --mode=perf,
      will produce a perf.csv file.

      This script takes perf.csv as its input and runs the performance testing
      grading algorithm to return a single CSV row, indicating the perf scores
      for each team.

      The intention is that the single row be manually copy and pasted into the
      row output by the grade.py script.
================================================================================
"""
import sys
import argparse
import csv
import numpy as np
from pathlib import Path
from typing import List
from dragon_runner.scripts.base import Script


class GradePerfScript(Script):

    @classmethod
    def name(cls) -> str:
        return "grade-perf"

    @classmethod
    def description(cls) -> str:
        return "Grade performance testing results"

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="grade-perf",
            description="Grade performance testing results"
        )
        parser.add_argument(
            "perf_csv",
            type=Path,
            help="Path to csv file generated from grade mode"
        )
        parser.add_argument(
            "output_csv",
            type=Path,
            help="Path to final output csv with grades"
        )
        return parser

    @staticmethod
    def grade_perf(*args):
        if len(args) < 2:
            print("Must supply two arguments: <perf_csv> <output_csv>")
            return 1

        with open(args[0], "r") as perf_csv:
            reader = csv.reader(perf_csv)
            headers = next(reader)
            test_data = [row for row in reader if row and any(row)]

        raw_times = np.array([[float(x) for x in row[1:]] for row in test_data])

        scores = []
        for times in raw_times:
            fastest_time = min(times)
            test_scores = [fastest_time / time for time in times]
            scores.append(test_scores)
        total_scores = np.mean(scores, axis=0)

        print(headers[1:])
        print(total_scores)

        # Write results to output CSV
        with open(args[1], "w") as output_csv:
            writer = csv.writer(output_csv)
            writer.writerow(headers[1:])
            writer.writerow(total_scores)

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)
        cls.grade_perf(parsed_args.perf_csv, parsed_args.output_csv)
        return 0

if __name__ == "__main__":
    sys.exit(GradePerfScript.main(sys.argv[1:]))
    
