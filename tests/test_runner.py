
# test_toolchain.py
from dragon_runner.runner import ToolChainRunner, TestResult
from dragon_runner.config import Config

def run_tests_for_config(config: Config, expected_result: bool):
    assert config.packages is not None
    
    for exe in config.executables:
        for tc in config.toolchains:
            tc_runner = ToolChainRunner(tc, timeout=3.0)
            for pkg in config.packages:
                for sp in pkg.subpackages:
                    for test in sp.tests:
                        result: TestResult = tc_runner.run(test, exe)
                        assert result.did_pass == expected_result

def test_gcc_toolchain_success(config_factory):
    config = config_factory("gccPassConfig.json")
    run_tests_for_config(config, expected_result=True)

def test_cat_toolchain_success(config_factory):
    config = config_factory("catConfig.json")
    run_tests_for_config(config, expected_result=True)

def test_gcc_toolchain_failures(config_factory):
    config = config_factory("gccFailConfig.json")
    run_tests_for_config(config, expected_result=False)