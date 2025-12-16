"""
This script must run with symmetric tables, meaning nrows = ncols.
"""
import sys
import argparse
import csv
from pathlib import Path
from fractions import Fraction
from typing import List
from dragon_runner.scripts.base import Script


class GradeScript(Script):

    DEFENSIVE_PTS = 2
    OFFENSIVE_PTS = 1
    COHERENCE_PTS = 10
    COMPETITIVE_WEIGHT = 0.2
    TA_WEIGHT = 0.5

    @classmethod
    def name(cls) -> str:
        return "grade"

    @classmethod
    def description(cls) -> str:
        return "Grade tournament results and compute scores"

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="grade",
            description="Grade 415 tournament results"
        )
        parser.add_argument("tournament_csvs", type=Path, nargs="+",
                          help="Path(s) to tournament CSV files")
        parser.add_argument("output_csv", type=Path,
                          help="Path to output CSV file")
        parser.add_argument("--solution-name", type=str, default="solution",
                          help="Name of the solution/TA executable in the CSV (default: 'solution')")
        return parser

    @staticmethod
    def parse_fraction(s):
        try:
            return round(float(Fraction(s)), 4)
        except (ValueError, ZeroDivisionError):
            return round(float(s), 4) if s else 0.0

    @staticmethod
    def load_csv(filepath):
        with open(filepath, 'r') as f:
            return list(csv.reader(f))

    @classmethod
    def average_tables(cls, tables):
        table = tables[0]
        n_rows = len(table)
        n_cols = len(table[0])
        assert n_rows == n_cols, f"Expected table to be symmetric! Found {n_rows} rows and {n_cols} columns"

        avg_table = [row[:] for row in tables[0]]
        avg_table[0][0] = "toolchain_summary"
        for j in range(1, n_cols):
            for i in range(1, n_rows):
                avg_cell = 0
                for table in tables:
                    avg_cell += cls.parse_fraction(table[i][j])
                avg_table[i][j] = round(avg_cell / len(tables), 2)
        return avg_table

    @classmethod
    def compute_tournament_points(cls, table, solution_name):
        n_rows = len(table)
        n_cols = len(table[0])
        solution_col = None
        for j in range(1, n_cols):
            if table[0][j].lower() == solution_name.lower():
                solution_col = j
                break

        print(f"{n_rows}:{n_cols}")
        print(f"Computing tournament with solution '{table[0][solution_col]}' at column: {solution_col}")
        scores = {
            'defensive': [],
            'offensive': [],
            'coherence': [],
            'ta': []
        }
        for j in range(1, n_cols):
            d_score = 0
            o_score = 0
            c_score = 0
            ta_score = 0
            c_score = cls.COHERENCE_PTS if cls.parse_fraction(table[j][j]) == 1 else 0
            if solution_col is not None and solution_col < len(table[j]):
                ta_score = cls.parse_fraction(table[j][solution_col])

            for i in range(1, n_rows):
                if i != j:
                    d_score += cls.DEFENSIVE_PTS * cls.parse_fraction(table[j][i])

            for k in range(1, n_cols):
                if k != j and k < len(table[j]):
                    o_score += cls.OFFENSIVE_PTS * (1 - cls.parse_fraction(table[k][j]))

            scores['defensive'].append(round(d_score, 2))
            scores['offensive'].append(round(o_score, 2))
            scores['coherence'].append(c_score)
            scores['ta'].append(ta_score)

        print(scores)
        return scores

    @classmethod
    def create_summary_table(cls, base_table, avg_scores):
        summary = [["toolchain summary"] + base_table[0][1:]]

        for i in range(1, len(base_table)):
            if i < len(base_table[0]):
                row = [base_table[i][0]]
                for j in range(1, len(base_table[0])):
                    if i < len(base_table) and j < len(base_table[i]):
                        row.append(round(cls.parse_fraction(base_table[i][j]), 3))
                    else:
                        row.append(0)
                summary.append(row)

        competitive_total = []
        for i in range(len(avg_scores['defensive'])):
            total = (avg_scores['defensive'][i] +
                    avg_scores['offensive'][i] +
                    avg_scores['coherence'][i])
            competitive_total.append(total)

        max_score = max(competitive_total) if competitive_total else 1

        summary.append(["Defensive Points"] + [f"{s:.2f}" for s in avg_scores['defensive']])
        summary.append(["Offensive Points"] + [f"{s:.2f}" for s in avg_scores['offensive']])
        summary.append(["Coherence Points"] + [f"{s:.0f}" for s in avg_scores['coherence']])
        summary.append(["Competitive Points"] + [f"{s:.2f}" for s in competitive_total])
        summary.append(["TA Testing Score (50% Weight)"] +
                       [f"{s * cls.TA_WEIGHT:.3f}" for s in avg_scores['ta']])
        normalized = [cls.COMPETITIVE_WEIGHT * (s / max_score) for s in competitive_total]
        summary.append(["Normalized Points (20% Weight)"] + [f"{s:.3f}" for s in normalized])
        return summary

    @classmethod
    def grade(cls, toolchain_paths, output_path, solution_name):
        tables = [cls.load_csv(path) for path in toolchain_paths]
        avg_table = cls.average_tables(tables)
        scores = cls.compute_tournament_points(avg_table, solution_name)

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            for table in tables:
                writer.writerows(table)
                writer.writerow([])
            writer.writerows(cls.create_summary_table(avg_table, scores))

        print(f"Grading complete. Output written to {output_path}")
        print(f"Solution name used: '{solution_name}'")
        return 0

    @classmethod
    def main(cls, args: List[str]) -> int:
        parser = cls.get_parser()
        parsed_args = parser.parse_args(args)
        return cls.grade(parsed_args.tournament_csvs, parsed_args.output_csv, parsed_args.solution_name)

if __name__ == "__main__":
    sys.exit(GradeScript.main(sys.argv[1:]))
