from colorama               import Fore
from typing                 import List
from dragon_runner.cli      import CLIArgs
from dragon_runner.config   import Config
from dragon_runner.log      import log, log_delimiter
from dragon_runner.testfile import TestFile
from dragon_runner.runner   import ToolChainResult, TestResult, ToolChain, ToolChainRunner
from dragon_runner.runner   import get_test_result

class TestHarness:
    def __init__(self, config: Config, cli_args: CLIArgs):
        self.config                     = config
        self.cli_args                   = cli_args
        self.failures: List[TestFile]   = []

    def log_failures(self) -> str:
        log(f"Failure Summary: ({len(self.failures)} tests)")
        for test in self.failures:
            log(Fore.RED + "[FAILED] " + Fore.RESET + test.file, indent=2)

    def run_regular(self) -> bool:
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
                tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
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
                                    self.log_result(test, test_result)
                                    sp_pass_count += 1
                                else:
                                    self.failures.append(test)
                                    log(test_result.diff, level=1)
                                    self.log_result(test, test_result)
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

    def run(self) -> bool:
        """
        decide wether to run in regular mode or grade mode based on the CLI args 
        """ 
        if self.cli_args.grade_file:
            assert self.cli_args.failure_log is not None, "Need to supply failure log!"
            log("Run grader") 
            return self.run_grader_json()
        else:
            log("Run regular") 
            return self.run_regular()

    def run_grader_json(self):
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        For now emit JSON to work with the existing grader script.
        TODO: Make the entire grading process self-contained here.
        """ 
        log("Running in grade mode")

        attacking_pkgs = [pkg for pkg in self.config.packages]
        defending_exes = [exe for exe in self.config.executables]
        
        for toolchain in self.config.toolchains:
            tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)

            print(f"toolchain: {toolchain.name}")
            for d_exe in defending_exes:
                
                print(f"  defender: {d_exe.id}") 
                with open(f"{d_exe.id}-feedback.txt", 'w+') as def_f:
                    
                    for a_pkg in attacking_pkgs: 
                        print(f"    ({a_pkg.name}) -> ({d_exe.id}) ", end='')
                        for a_spkg in a_pkg.subpackages:
                            for test in a_spkg.tests:
                                d_result : ToolChainResult = tc_runner.run(test, d_exe)
                                if not d_result.success:
                                    print('x', end='')
                                else:
                                    test_result: TestResult = get_test_result(d_result, test.expected_out)
                                    if test_result.did_pass:
                                        print('.', end='')
                                    else:
                                        print('x', end='')
                        print("")

    def log_result(self, test: TestFile, result: TestResult):
        if result.did_pass:
            status = "[E-PASS]" if result.error_test else "[PASS]"
            time_str = f"{result.time:.5f}s" if result.time and self.cli_args.time else ""
            log(f"{Fore.GREEN}{status:<10}{Fore.RESET}{test.file:<48}{time_str}", indent=2)
        else:
            status = "[FAIL]" if result.error_test else "[E-FAIL]"
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
