"""
============================== 415 Grading Script ==============================
Author: Justin Meimar 
Name: add_empty.py
Desc: 
================================================================================
"""
import argparse
import random
import string
from pathlib import Path

def load_key(key_path):
    config = {}
    with open(key_path) as key_file:
        for line in key_file.readlines():
            sid, gh_username = line.strip().split(' ')
            print("SID: ", sid, "\tGH Username: ", gh_username)
            config[sid] = gh_username
    print("Config Loaded...") 
    return config

def count_files_with_exclusions(directory: Path, excluded_extensions: list) -> int:
    count = 0
    for path in directory.rglob('*'):
        if path.is_file():
            if path.suffix.lower() not in excluded_extensions:
                count += 1
    return count

def add_empty(key_file: Path, search_path: Path, empty_content: str):
    """
    """
    config = load_key(key_file) 

    if not search_path.is_dir():
        error = "Could not create test directory."
        print(error)
        return 1
    
    all_fine = True
    for (sid, gh_user) in config.items():
        all_matches = list(search_path.rglob(sid))
        if len(all_matches) == 0:
            print(f"Can not find a directory matching: {sid} in {search_path.name}")
            exit(1)
        if len(all_matches) > 1:
            print(f"Found several matches for what should be a unique directory named {sid}:")
            for m in all_matches:
                print("Matched: ", m)
            exit(1)
        
        sid_test_dir = Path(all_matches[0])
        assert sid_test_dir.is_dir() and sid_test_dir.exists() and f"{sid_test_dir} should exist."
        
        test_count = 0 
        for path in sid_test_dir.rglob("*"):
            if path.is_file() and not path.is_dir() and not path.name.startswith('.'):
                if path.suffix.lower() not in [".ins", ".out"]:
                    test_count += 1
        
        if test_count >= 5:
            continue
        
        all_fine = False
        # Here if the submitted directory has less than 5 tests.
        while test_count < 5:
            suffix= ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            file_path = sid_test_dir / f"TA_empty_{test_count+1}_{suffix}.in"
            file_path.write_text(empty_content)
            test_count += 1 
            print(f"{sid} - Writing an empty file: {file_path.name}...")
    
    if all_fine:
        print("All students submited at least five testcases!")

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("key_file", type=Path, help="Key file which has a line for each (SID, GH_Username) pair")
    parser.add_argument("search_path", type=Path, help="Path to search for test files")
    parser.add_argument("empty_content", type=str, help="Empty content to write into files")
    args = parser.parse_args()

    add_empty(args.key_file, args.search_path, args.empty_content)

