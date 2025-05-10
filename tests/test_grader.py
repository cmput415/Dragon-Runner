import os
from dragon_runner.src.harness import TournamentHarness
from dragon_runner.src.config import Config
from dragon_runner.src.cli import RunnerArgs

def test_grader_config(config_factory, cli_factory):

    config : Config = config_factory("ConfigGrade.json")
    args : RunnerArgs = cli_factory(**{
        "mode": "tournament",
        "failure_log": "Failures.txt",
        "timeout": 2
    })
    
    harness = TournamentHarness(config=config, cli_args=args) 
    assert harness is not None
    
    harness.run()
    assert os.path.exists(args.failure_log)

