from colorama               import init, Fore
from typing                 import List
from dragon_runner.config   import Config
from dragon_runner.log      import log, log_multiline
from dragon_runner.utils    import bytes_to_str
from dragon_runner.testfile import TestFile
from dragon_runner.runner   import ToolChainResult, TestResult, ToolChain, ToolChainRunner
from dragon_runner.runner   import get_test_result

def log_result(test: TestFile, result: TestResult):
    if result.did_pass:
        status = "[ERROR PASS]" if result.error_test else "[PASS]"
        time_str = f"{result.time:.5f}s" if result.time else ""
        log(f"{Fore.GREEN}{status:<15}{Fore.RESET}{test.file:<48}{time_str}")
    else:
        status = "[FAIL]" if result.error_test else "[ERROR FAIL]"
        log(f"{Fore.RED}{status:<15}{Fore.RESET}{test.file}")

def log_toolchain_result(test: TestFile, result: ToolChainResult, tc: ToolChain):
    """
    log relevant info when the toolchain panics at some intermediate step
    """
    if result.success:
        return
    log(Fore.RED + "[TOOLCHAIN ERROR] " + Fore.RESET + test.file)
    log("Failed on step: ", result.last_step.name, indent=2, level=1)
    log("Exited with status: ", result.exit_code, indent=2, level=1)
    log("With command: ", result.last_step.exe_path, indent=2, level=1)
    log(f"With stderr: ({len(result.stderr.getbuffer())} bytes)", indent=2, level=1)
    log_multiline(bytes_to_str(result.stderr), indent=4, level=1)
    log(f"With stdout: ({len(result.stdout.getbuffer())} bytes)", indent=2, level=1)
    log_multiline(bytes_to_str(result.stdout), indent=4, level=1)

class TestHarness:
    def __init__(self, config: Config):
        self.config = config
        self.failures: List[TestFile]= []

    def log_failures(self) -> str:
        log(f"Failure Summary: ({len(self.failures)} tests)")
        for test in self.failures:
            log(Fore.RED + "[FAILED] " + Fore.RESET + test.file, indent=2)

    def run_all(self, timeout: float) -> bool:
        """
        Iterate over all tested executables, toolchains, subpackages and tests.
        Return True is all pass, false otherwise.
        """ 
        sucecss = True
        for exe in self.config.executables:
            log("Running executable:\t", exe.id)
            exe.source_env()
            exe_pass_count = 0
            exe_test_count = 0
            for toolchain in self.config.toolchains:
                tc_runner = ToolChainRunner(toolchain, timeout)
                log("Running Toolchain:\t", toolchain.name)
                tc_pass_count = 0
                tc_test_count = 0
                for spkg in self.config.sub_packages:
                    log(f"Entering subpackage {spkg.package_name}")
                    sp_pass_count = 0
                    sp_test_count = 0
                    for test in spkg.tests:
                        tc_result : ToolChainResult = tc_runner.run(test, exe)
                        if not tc_result.success:
                            self.failures.append(test)
                            log_toolchain_result(test, tc_result, toolchain, )
                            sp_test_count +=1 
                        else:
                            test_result: TestResult = get_test_result(tc_result, test.expected_out)
                            if test_result.did_pass:
                                log_result(test, test_result)
                                sp_pass_count += 1
                            else:
                                self.failures.append(test)
                                log(test_result.diff, level=1)
                                log_result(test, test_result)
                            sp_test_count +=1 
                    log("Subpackage Passed: ", sp_pass_count, "/", sp_test_count)
                    tc_pass_count += sp_pass_count
                    tc_test_count += sp_test_count
                log("Toolchain Passed: ", tc_pass_count, "/", tc_test_count)
                exe_pass_count += tc_pass_count
                exe_test_count += tc_test_count
            log("Executable Passed: ", exe_pass_count, "/", exe_test_count)
            if exe_pass_count != exe_test_count:
                sucecss = False
        return sucecss