#
# Quick script 
#
#

import os
import subprocess
from pathlib import Path

if __name__ == "__main__":

    script_dir = Path(__file__).parent.absolute()
    for file in os.listdir(script_dir):
        if "test_" in file:
            print(file)
            subprocess.run(f"pytest {os.path.join(script_dir, file)}", shell=True)

