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
from typing     import List

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
    # n_rows = len(tc_table)
    # n_cols = len(tc_table[0])    

    print("TC_TABLE", tc_table)
    print("COMPETITIVE ROW:", tc_table[-2][1:])
    raw_competitive_scores = tc_table[-2][1:]
    max_score = max(raw_competitive_scores)
    print("MAX SCORE: ", max_score)
    norm_competitive_scores = [
        round(COMPETITIVE_WEIGHT * (float(score) / float(max_score)), 3)
        for score in raw_competitive_scores
    ]
    norm_scores_row = ["Normalized Points (20% Weight)"] + norm_competitive_scores
    tc_table.append(norm_scores_row)

def average_toolchain_tables(tables):
    """
    Take a number of identical toolchain tables and return the average
    of all their values. 
    """ 
    n_rows = len(tables[0])
    n_cols = len(tables[0][0])
    for table in tables:
        assert len(table) == n_rows, "num rows differ"
        assert len(table[0]) == n_cols, "num cols differ"
    
    avg_table = [row[:] for row in tables[0]]
    avg_table[0][0] = "toolchain summary" 
    for i in range(1, n_cols):
        for j in range(1, n_cols):
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
    n_cols = len(table[0])
    print("N_COLS:", n_cols)
    print("N_ROWS:", len(table))
    
    # Declare new rows
    ta_points_row = ["TA Testing Score (50% Weight)"] + [0] * (n_cols - 1)
    defensive_row = ["Defensive Points"] + [0] * (n_cols - 1)
    offensive_row = ["Offensive Points"] + [0] * (n_cols - 1)
    coherence_row = ["Coherence Points"] + [0] * (n_cols - 1)
    total_row = ["Competitive Points"] + [0] * (n_cols - 1)

    for j in range(1, n_cols):
        attacker = table[0][j]
        ta_score = 0 # score on "solution" package
        o_score = 0 # offensive score
        d_score = 0 # defensive score
        c_score = 0 # coherence score
        c_score += COHERENCE_PTS if to_float(table[j][j]) == 1 else 0

        # defender = table[1][0]
        for i in range(1, n_cols):
            defender = table[i][0]
            print(f"i: {i}", defender)
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
        total_row[j] = str(
                float(defensive_row[j]) + float(offensive_row[j]) + float(coherence_row[j]))

    # Append new rows to the table
    table.append(defensive_row)
    table.append(offensive_row)
    table.append(coherence_row)
    table.append(total_row)
    table.append(ta_points_row)

    return table

def tournament(tournament_csv_paths: List[str], grade_path: str):
    """
    Run the tournament for each tournament csv then average all the
    toolchain tables. Write all the tables including the average to 
    the final grade_path
    """
    tc_tables = [] 
    for file in tournament_csv_paths:
        with open(file, 'r') as f:
            reader = csv.reader(f)
            tc_table = list(reader)
            tc_tables.append(add_competitive_rows(tc_table))
    
    print(tc_tables)
    tc_avg = average_toolchain_tables(tc_tables)
    normalize_competetive_scores(tc_avg)
    print(tc_avg)

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
    tournament(args.tournament_csvs, args.log_file)
    
    #
    # input_files = ['Grades.csv'] 
    # tc_tables = [] 
    # for file in input_files:
    #     with open(file, 'r') as f:
    #         reader = csv.reader(f)
    #         tc_table = list(reader)
    #         tc_tables.append(add_competitive_rows(tc_table))
    # 
    # print(tc_tables)
    # tc_avg = average_toolchain_tables(tc_tables)
    # normalize_competetive_scores(tc_avg)
    # print(tc_avg)
    #
    # output_file = './vcalc-grades.csv'
    # with open(output_file, 'w') as f:
    #     writer = csv.writer(f)
    #     for table in tc_tables:
    #         writer.writerows(table)
    #         writer.writerow([]) # newline
    #     writer.writerows(tc_avg)


