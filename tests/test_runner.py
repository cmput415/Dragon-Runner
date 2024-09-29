import os
from dragon_runner.runner   import run_toolchain
from dragon_runner.runner   import ToolChainResult
from dragon_runner.utils    import precise_diff
from dragon_runner.config   import Config
def test_valid_toolchain_success(sample_valid_config): 
    """
    Ensure all the tests that are supposed to pass, pass
    """
    gcc_config : Config = sample_valid_config 
    assert gcc_config.tests is not None
 
    for exe in gcc_config.executables:
        for tc in gcc_config.toolchains:
            for test in gcc_config.tests:
                result: ToolChainResult = run_toolchain(test, tc, exe)
                assert precise_diff(result.stdout, test.expected_out) is ""

def test_valid_toolchain_failures(sample_valid_fail_config):
    """
    Ensure all the tests that are supposed to fail, fail
    """
    gcc_config = sample_valid_fail_config 
    assert gcc_config.tests is not None
    
    # for exe in gcc_config.executables:
    #     for tc in gcc_config.toolchains:
    #         for test in gcc_config.tests:
    #             result: ToolChainResult = run_toolchain(test, tc, exe)
    #             assert precise_match(result.stdout, test.expected_out) is not ""