
from typing import List
from dragon_runner.scripts.build import build 
from dragon_runner.scripts.grade import grade 
from dragon_runner.scripts.gather import gather 
from dragon_runner.scripts.gen_config import main as gen_config 
from dragon_runner.scripts.grade_perf import grade_perf

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
            "gen-config":   lambda: gen_config(*self.args),
            "grade":        lambda: grade(*self.args),
            "grade-perf":   lambda: grade_perf(*self.args),
            "anon-tests":   lambda: print("TODO"),
            "anon-csv":     lambda: print("TODO"),
            "preview":      lambda: print("TODO")
        }
    
        try:
            print(f"Running: {self.script} with args {self.args}")  
            script_dispatch.get(self.script, lambda: unknown_script)()

        except Exception as e:
            print(f"Failed to run script: {e}")
 
