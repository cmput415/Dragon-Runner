import csv
from fractions import Fraction

DEFENSIVE_PTS       = 2
OFFENSIVE_PTS       = 1
COHERENCE_PTS       = 1
COMPETITIVE_WEIGHT  = 0.2
TA_WEIGHT           = 0.5
SOLUTION            = "solution"

def normalize_competetive_scores(tc_table):
    """
    Normalize the competative scores of a table relative to the max score.
    By convention the last row contains the total score for the toolchain  
    """
    n_rows = len(tc_table)
    competitive_scores = tc_table[n_rows-1][1:]
    max_score = max(competitive_scores) 
    norm_competitive_scores = [
        round(COMPETITIVE_WEIGHT * (score / max_score), 3)
        for score in competitive_scores
    ]
    tc_table[-1] = norm_competitive_scores
    # print(tc_table[-1])

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

    avg_table = tables[0]
    for i in range(1, n_rows):
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

    # Declare new rows
    ta_points_row = ["TA Testing Score"] + [0] * (n_cols - 1)
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

        for i in range(1, len(table)):            
            defender = table[i][0]
            if defender == SOLUTION:
                # look at the transpose position to determine TA score
                ta_score += to_float(table[j][i])

            o_score += (1 - to_float(table[i][j]))
            d_score += (2 if to_float(table[j][i]) == 1 else 0)

        # print(f"attacker: {attacker}\n oscore: {o_score} \ndscore: {d_score}\n cscore: {c_score}")

        # Populate the new rows
        ta_points_row[j] = round(ta_score, 3)
        defensive_row[j] = round(d_score * DEFENSIVE_PTS, 2)
        offensive_row[j] = round(o_score * OFFENSIVE_PTS, 2)
        coherence_row[j] = round(c_score, 3)
        total_row[j] = defensive_row[j] + offensive_row[j] + coherence_row[j]

    # Append new rows to the table
    table.append(ta_points_row)
    table.append(defensive_row)
    table.append(offensive_row)
    table.append(coherence_row)
    table.append(total_row)

    return table

if __name__ == "__main__":

    input_files = ['riscv.csv', 'x86.csv', 'arm.csv', 'interpreter.csv'] 
    tc_tables = [] 
    for file in input_files:
        with open(file, 'r') as f:
            reader = csv.reader(f)
            tc_table = list(reader)
            tc_tables.append(add_competitive_rows(tc_table))

    tc_avg = average_toolchain_tables(tc_tables)
    normalize_competetive_scores(tc_avg)

# --------------------------------------------------------------------------- #
def to_float(to_convert) -> float:
    """
    Helper function to convert fraction strings to floating point
    """
    try:
        return float(Fraction(to_convert))
    except ValueError:
        return float(to_convert)

