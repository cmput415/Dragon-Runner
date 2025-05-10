from dragon_runner.src.runner   import ToolChainRunner, TestResult
from dragon_runner.src.config   import Config
import sys
import os
import subprocess

TEST_DIR            = os.path.dirname(os.path.abspath(__file__))
COMPILE_LIB_SCRIPT  = f"{TEST_DIR}/scripts/test-scripts/compile_lib.py"
LIB_SRC_DIR         = os.path.join(TEST_DIR, "lib/src")
LIB_OUT_DIR         = os.path.join(TEST_DIR, "lib")

def run_tests_for_config(config: Config, expected_result: bool):
    # TODO: move to conftest.py
    assert config.packages is not None

    for exe in config.executables:
        exe.source_env()
        for tc in config.toolchains:
            tc_runner = ToolChainRunner(tc, timeout=3.0)
            for pkg in config.packages:
                for sp in pkg.subpackages:
                    for test in sp.tests:
                        result: TestResult = tc_runner.run(test, exe)
                        result.log()
                        assert result.did_pass == expected_result


def test_gcc_toolchain_success(config_factory, cli_factory):
    assert os.path.exists(COMPILE_LIB_SCRIPT), "missing library compiler script" 

    if sys.platform == "darwin":
        lib = "libfib.dylib"
        config = config_factory("runtimeConfigDarwin.json")
    else:
        lib = "libfib.so"
        config = config_factory("runtimeConfigLinux.json")

    expected_lib=os.path.join(TEST_DIR, f"lib/{lib}")

    if not os.path.exists(expected_lib):
        result = subprocess.run([sys.executable,
                                COMPILE_LIB_SCRIPT,
                                LIB_SRC_DIR,
                                LIB_OUT_DIR], check=True)
        
        assert result.returncode == 0, "shared object compilation failed"
        assert os.path.exists(expected_lib), "failed to create shared object"

    # now shared object exists where the config expects it, so we can run
    os.environ["DRAGON_RUNNER_DEBUG"] = "3"
    run_tests_for_config(config, expected_result=True)
