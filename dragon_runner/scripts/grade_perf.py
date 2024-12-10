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
import argparse
import csv
import numpy as np
from pathlib    import Path 

def grade_perf(*args):
    """
    Run the tournament for each tournament csv then average all the
    toolchain tables. Write all the tables including the average to 
    the final grade_path
    """

    if len(args) < 2:
        print("Must supply two arguments: <perf_csv> <output_csv>")
        return 1

    with open(args[0], "r") as perf_csv:
        reader = csv.reader(perf_csv)
        headers = next(reader)
        test_data = list(reader)

    # test_names = [row[0] for row in test_data]
    raw_times = np.array([[float(x) for x in row[1:]] for row in test_data])
     
    scores = []
    for times in raw_times:
        fastest_time = min(times)
        test_scores = [fastest_time / time for time in times]
        scores.append(test_scores)
    total_scores = np.mean(scores, axis=0)
    
    print(headers[1:])
    print(total_scores)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "perf_csv",
        type=Path,
        nargs="+",
        help="Path to one or more csv files generated from grade mode"
    )
    parser.add_argument(
        "output_csv",
        type=Path,
        help="Path to final output csv with grades"
    )
    
    args = parser.parse_args() 
    grade_perf(args.perf_csv, args.output_csv)
    
