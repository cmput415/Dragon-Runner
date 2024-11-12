import subprocess
from typing import List

from dragon_runner.scripts.build_script import build 
from dragon_runner.scripts.gather_script import gather 

class Loader:

    def __init__(self, script: str, args: List[str]):
        self.script = script 
        self.args = args

    def run(self):
         
        print(f"Running: {self.script} with args {self.cmd}")

        # if self.script == "build":
            # cmd = ["python3", "build_script.py"] 
        # build_script 
        # subprocess.run(self.cmd, shell=True) 
