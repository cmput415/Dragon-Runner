import os
from dragon_runner.harness import TestHarness
from dragon_runner.config import Config
from dragon_runner.cli import CLIArgs

def test_grader_config(config_factory, cli_factory):

    config : Config = config_factory("ConfigGrade.json")
    args : CLIArgs = cli_factory(**{
        "grade_file": "Grades.json",
        "failure_file": "Failures.txt"
    })
    
    harness = TestHarness(config=config, cli_args=args) 
    assert harness is not None
    
    harness.run()
    assert os.path.exists(args.grade_file)
