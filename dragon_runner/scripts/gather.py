import shutil
import argparse
from pathlib import Path

def gather(ccids_file: str,
           search_path: str,
           project_name: str,
           output_dir: str = "submitted-testfiles"):
    """
    Gather all the testfiles in student directories. Look for directories in
    @search_path that contain @project_name. Inside each project look for
    tests/testfiles/TEAM_NAME and copy it out.
    """
    search_dir = Path(search_path)
     
    if not search_dir.is_dir():
        error = "Could not create test directory."
        print(error)
        return 1
    
    directories = [d for d in search_dir.iterdir() if d.is_dir() and project_name in d.name]
    ccids = Path(ccids_file).read_text().splitlines()
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for dir_path in directories:
        for ccid in ccids:
            if ccid in str(dir_path):
                expected_test_dir = dir_path / "tests" / "testfiles" / ccid
                if expected_test_dir.is_dir():
                    print(f"-- Found properly formatted testfiles for {ccid}")
                    shutil.copytree(expected_test_dir, output_path / ccid, dirs_exist_ok=True)
                else:
                    print(f"-- Could NOT find testfiles for {ccid}")
 
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("ccids_file", type=Path, help="File containing CCIDs")
    parser.add_argument("search_path", type=Path, help="Path to search for test files")
    parser.add_argument("project_name", type=Path, help="Path to search for test files")
    args = parser.parse_args()
    
    gather(args.ccids_file, args.search_path, args.project_name)

