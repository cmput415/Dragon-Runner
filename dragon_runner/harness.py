from colorama               import Fore
from typing                 import List
from dragon_runner.config   import Config
from dragon_runner.log      import log, log_delimiter
from dragon_runner.testfile import TestFile
from dragon_runner.runner   import ToolChainResult, TestResult, ToolChain, ToolChainRunner
from dragon_runner.runner   import get_test_result

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
                for pkg in self.config.packages:
                    log(f"Entering package {pkg.name}")
                    for spkg in pkg.subpackages:
                        log(f"Entering subpackage {spkg.name}", indent=1)
                        sp_pass_count = 0
                        sp_test_count = 0
                        for test in spkg.tests:
                            tc_result : ToolChainResult = tc_runner.run(test, exe)
                            if not tc_result.success:
                                self.failures.append(test)
                                log_toolchain_failure(test, tc_result, toolchain, )
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
    
    def grade_all(self, timeout: float):
        """
        Iterate over all tested executables, toolchains, subpackages and tests.
        Return True is all pass, false otherwise.
        """ 
        sucecss = True
        for exe in self.config.executables:
            log("Calculating grade for :\t", exe.id)

def log_result(test: TestFile, result: TestResult):
    if result.did_pass:
        status = "[ERROR PASS]" if result.error_test else "[PASS]"
        time_str = f"{result.time:.5f}s" if result.time else ""
        log(f"{Fore.GREEN}{status:<20}{Fore.RESET}{test.file:<48}{time_str}", indent=2)
    else:
        status = "[FAIL]" if result.error_test else "[ERROR FAIL]"
        log(f"{Fore.RED}{status:<20}{Fore.RESET}{test.file}", indent=2)

def log_toolchain_failure(test: TestFile, result: ToolChainResult, tc: ToolChain):
    """
    log relevant info when the toolchain panics at some intermediate step
    """
    status = "[TOOLCHAIN ERROR]"
    log(f"{Fore.RED}{status:<20}{Fore.RESET}{test.file}", indent=2)
    log_delimiter(title=f"Failed on toolchain: {tc.name}", indent=2, level=1)
    log(f"Failed on step: {result.last_step.name}", indent=4, level=1) 
    log(f"Exited with status: {result.exit_code}", indent=4, level=1)
    log(f"Stderr: {result.stderr.getvalue()}", indent=4, level=1)
