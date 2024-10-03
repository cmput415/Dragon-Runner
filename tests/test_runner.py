import os
from dragon_runner.runner   import ToolChainRunner, TestResult
from dragon_runner.config   import Config

def test_valid_toolchain_success(sample_valid_config): 
    """
    Ensure all the tests that are supposed to pass, pass
    """
    gcc_config : Config = sample_valid_config 
    assert gcc_config.packages is not None
 
    for exe in gcc_config.executables:
        for tc in gcc_config.toolchains:
            tc_runner = ToolChainRunner(tc, timeout=5.0)
            for pkg in gcc_config.packages:
                for sp in pkg.subpackages:
                    for test in sp.tests:
                        result: TestResult = tc_runner.run(test, exe)
                        assert result.did_pass

def test_valid_toolchain_failures(sample_valid_fail_config):
    """
    Ensure all the tests that are supposed to fail, fail
    """
    gcc_config : Config = sample_valid_fail_config 
    assert gcc_config.packages is not None
  
    for exe in gcc_config.executables:
        for tc in gcc_config.toolchains:
            tc_runner = ToolChainRunner(tc, timeout=5.0)
            for pkg in gcc_config.packages:
                for sp in pkg.subpackages:
                    for test in sp.tests:
                        result: TestResult = tc_runner.run(test, exe)
                        assert not result.did_pass

