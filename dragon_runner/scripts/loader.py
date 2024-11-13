
from typing import List
from dragon_runner.scripts.build import build 
from dragon_runner.scripts.gather import gather 

class Loader:
    """
    Dragon runner allows grading scripts to be run through its CLI.
    """

    def __init__(self, script: str, args: List[str]):
        self.script = script 
        self.args = args
        self.errors = []
        
    def run(self):
        """
        Select the script to run from the mode argument passed through
        dragon-runner CLI.
        """
        def unknown_script():
            print(f"script: {self.script} did not match any registered script.")

        script_dispatch = {
            "build":        lambda: build(*self.args),
            "gather":       lambda: gather(*self.args),
            "anon-tests":   lambda: print("TODO"),
            "anon-csv":     lambda: print("TODO"),
            "preview":      lambda: print("TODO")
        }
    
        try:
            print(f"Running: {self.script} with args {self.args}")  
            script_dispatch.get(self.script, lambda: unknown_script)()

        except Exception as e:
            print(f"Failed to run script: {e}")
 
