import os
import shutil
import re
import argparse

def anonymize_files(input_dir, output_dir, ccid_map):
    
    files = sorted([f for f in os.listdir(input_dir) if f.endswith('feedback.txt')])
    
    for file in files:
        ccid_portion, tc_portion = file.split('-')

        try:
            anon_key = ccid_map[ccid_portion]
        except KeyError:
            print(f"Failed to anonymoize: {ccid_portion}")
            continue

        print(ccid_portion, tc_portion)
        
        anon_file = anon_key + '-' + tc_portion
        shutil.copy(
            os.path.join(input_dir, file),
            os.path.join(output_dir, anon_file)
        )
        
        print(f"Anonymized: {file} as {anon_file}")

def fill_map(map_path):
    
    ccid_map = {}
    with open(map_path, 'r') as map:
        for line in map.readlines():
            key, value = line.split(' ')
            ccid_map[key] = value.strip()
   
    return ccid_map
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anonymize feedback files.")
    parser.add_argument("ccid_map_path", help="Path to the ccid-sid-map.txt file")
    parser.add_argument("input_dir", help="Path to the directory containing feedback files")
    parser.add_argument("output_dir", help="Path to the directory to put output files")
    
    args = parser.parse_args() 
    ccid_map = fill_map(args.ccid_map_path)
    anonymize_files(args.input_dir, args.output_dir, ccid_map)

