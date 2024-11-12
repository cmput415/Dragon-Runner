import subprocess
from typing import List

class Loader:

    def __init__(self, script: str, cmd: List[str]):
        self.script = script 
        self.cmd = cmd

    def run(self):
        
        print(f"Running: {self.script} with args {self.cmd}")
        subprocess.run(self.cmd, shell=True) 
