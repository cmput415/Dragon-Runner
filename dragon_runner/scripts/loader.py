from typing import List
from pathlib import Path
from dragon_runner.scripts.build import build 
# from dragon_runner.scripts.gather import gather 

class Loader:

    def __init__(self, script: str, args: List[str]):
        self.script = script 
        self.args = args

    def run(self):
            
        def unknown_script():
            print(f"script: {self.script} did not match any registered script.")

        print(f"Running: {self.script} with args {self.args}") 
        
        {
            "build": lambda: build(*self.args),
        }.get(self.script, lambda: unknown_script)()
        
 
