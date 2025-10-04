from typing import List
from dragon_runner.scripts.add_empty import add_empty
from dragon_runner.scripts.build import build 
from dragon_runner.scripts.grade import grade 
from dragon_runner.scripts.gather import gather 
from dragon_runner.scripts.gen_config import main as gen_config 
from dragon_runner.scripts.grade_perf import grade_perf
from dragon_runner.scripts.checkout import checkout
from dragon_runner.scripts.clean_build import clean_build

class Loader:
    """
    Dragon runner allows grading scripts to be run through its CLI.
    """
    def __init__(self): 
        self.script_dispatch = {
            "add_empty.py":         add_empty,
            "build.py":             build,
            "clean_build.py":       clean_build,
            "checkout.py":          checkout,
            "gather.py":            gather,
            "gen-config.py":        gen_config,
            "grade.py":             grade,
            "grade-perf.py":        grade_perf,
        }

    def __call__(self, script: str, args: List[str]):
        """
        Select the script to run from the mode argument passed through
        dragon-runner CLI.
        """
        try:
            print(f"Running: {script} with args {args}")
            if script not in self.script_dispatch:
                print(f"Script: {script} did not match any registered script.")
                print(self)
                return
                
            script_fn = self.script_dispatch[script]
            script_fn(*args)
            
        except Exception as e:
            print(f"Failed to run script: {e}")
    
    def __repr__(self):
        s = "Registered Scripts:\n"
        for script in self.script_dispatch.keys():
            s += f" - {script}\n"
        return s

