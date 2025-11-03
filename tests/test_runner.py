from dragon_runner.src.harness import RegularHarness
from dragon_runner.src.config import Config
from dragon_runner.src.cli import RunnerArgs

def test_gcc_pass(config_factory, cli_factory):

    config : Config = config_factory("gccPassConfig.json")
    args : RunnerArgs = cli_factory(**{
        "mode": "regular",
        "timeout": 10
    })
    
    harness = RegularHarness(config=config, cli_args=args) 
    assert harness is not None 
    success = harness.run()
    assert success == True

def test_gcc_pass_darwin(config_factory, cli_factory):

    config : Config = config_factory("catConfigDarwin.json")
    args : RunnerArgs = cli_factory(**{
        "mode": "regular",
        "timeout": 10
    })
    
    harness = RegularHarness(config=config, cli_args=args) 
    assert harness is not None 
    success = harness.run()
    assert success == True

def test_gcc_fail(config_factory, cli_factory):

    config : Config = config_factory("gccFailConfig.json")
    args : RunnerArgs = cli_factory(**{
        "mode": "regular",
        "timeout": 5
    })
    
    harness = RegularHarness(config=config, cli_args=args) 
    assert harness is not None 
    success = harness.run()
    assert success == False

