"""
============================== 415 Grading Script ==============================
Author: Justin Meimar 
Name: grade.py
Desc: 
================================================================================
"""
import argparse
import csv
from pathlib    import Path 
from fractions  import Fraction

# These are hard coded as to not bloat the CLI. Probably easier to change in place.
DEFENSIVE_PTS       = 2
OFFENSIVE_PTS       = 1
COHERENCE_PTS       = 10
COMPETITIVE_WEIGHT  = 0.2
TA_WEIGHT           = 0.5
SOLUTION            = "solution" # the EXE of the solution

def to_float(to_convert) -> float:
    """
    Helper function to convert fraction strings to floating point.
    """
    try:
        return float(Fraction(to_convert))
    except ValueError:
        return float(to_convert)

def normalize_competetive_scores(tc_table):
    """
    Normalize the competative scores of a table relative to the max score.
    By convention the last row contains the total score for the toolchain  
    """
    raw_competitive_scores = [float(score) for score in tc_table[-2][1:]]
    max_score = max(raw_competitive_scores)
    print("MAX SCORE: ", max_score, "FROM :", raw_competitive_scores)
    norm_competitive_scores = [
        round(COMPETITIVE_WEIGHT * (float(score) / float(max_score)), 3)
        for score in raw_competitive_scores
    ]
    norm_scores_row = ["Normalized Points (20% Weight)"] + norm_competitive_scores
    tc_table.append(norm_scores_row)

def average_toolchain_tables(tables, n_compilers):
    """
    Take a number of identical toolchain tables and return the average
    of all their values. 
    """ 
    print("N_COMPILERS: ", n_compilers)
    avg_table = [row[:] for row in tables[0]]
    avg_table[0][0] = "toolchain summary" 
    for i in range(1, n_compilers+1):
        for j in range(1, n_compilers+1):
            avg = 0 
            for tc in tables:
                avg += to_float(tc[i][j])
            avg = round(avg / len(tables), 3)
            avg_table[i][j] = avg

    return avg_table

def add_competitive_rows(table):
    """
    Add a row at the bottom of the table for defensive, offesnsive
    and coherence points. Not yet normalized to highest score. 
    """
    n_compilers = len(table)-1 # one row for labels 
    print(table)
    print("N_COMPILERS: ", n_compilers)

    # Declare new rows
    ta_points_row = ["TA Testing Score (50% Weight)"] + [0] * (n_compilers)
    defensive_row = ["Defensive Points"] + [0] * (n_compilers)
    offensive_row = ["Offensive Points"] + [0] * (n_compilers)
    coherence_row = ["Coherence Points"] + [0] * (n_compilers)
    total_row = ["Competitive Points"] + [0] * (n_compilers)

    for j in range(1, n_compilers+1):

        ta_score = 0 # score on "solution" package
        o_score = 0 # offensive score
        d_score = 0 # defensive score
        c_score = 0 # coherence score
        c_score += COHERENCE_PTS if to_float(table[j][j]) == 1 else 0

        # defender = table[1][0]
        for i in range(1, n_compilers+1):
            defender = table[i][0]
            if defender == SOLUTION:
                # look at the transpose position to determine TA score
                ta_score += to_float(table[j][i])

            o_score += (OFFENSIVE_PTS * (1 - to_float(table[i][j])))
            d_score += (DEFENSIVE_PTS * to_float(table[j][i]))

        # Populate the new rows
        ta_points_row[j] = str(round(ta_score * TA_WEIGHT, 3))
        defensive_row[j] = str(round(d_score, 2))
        offensive_row[j] = str(round(o_score, 2))
        coherence_row[j] = round(c_score, 3)
        total_row[j] = str(round(
                float(defensive_row[j]) + float(offensive_row[j]) + float(coherence_row[j]), 3))

    # Append new rows to the table
    table.append(defensive_row)
    table.append(offensive_row)
    table.append(coherence_row)
    table.append(total_row)
    table.append(ta_points_row)

    return table

def grade(*args):
    """
    Run the tournament for each tournament csv then average all the
    toolchain tables. Write all the tables including the average to 
    the final grade_path
    """
    
    if len(args) < 2:
        print("Must supply at least two arguments: <toolchain_csv>+ <grade_csv>")
        return 1
    
    # do some mangaling with args to be able to pass in variadic from loader.py
    toolchain_csv_paths = args[:-1]
    grade_path = args[-1]
    n_compilers = 0

    tc_tables = [] 
    for file in toolchain_csv_paths:
        with open(file, 'r') as f:
            reader = csv.reader(f)
            tc_table = list(reader)
            tc_tables.append(add_competitive_rows(tc_table))
    
    n_compilers = len(tc_tables[0][0]) - 1
    print("N COMPILERS: ", n_compilers)
    tc_avg = average_toolchain_tables(tc_tables, n_compilers)
    normalize_competetive_scores(tc_avg)
    
    with open(grade_path, 'w') as f:
        writer = csv.writer(f)
        for table in tc_tables:
            writer.writerows(table)
            writer.writerow([]) # newline
        writer.writerows(tc_avg)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "tournament_csvs",
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
    grade(*args.tournament_csvs, args.output_csv)
    
