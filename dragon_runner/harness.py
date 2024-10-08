import json
import pandas as pd
from colorama               import Fore
from typing                 import List
from dragon_runner.cli      import CLIArgs
from dragon_runner.config   import Config, Executable, Package
from dragon_runner.log      import log
from dragon_runner.testfile import TestFile
from dragon_runner.runner   import TestResult, ToolChainRunner
from dragon_runner.utils    import file_to_str

class TestHarness:
    __test__ = False 
    def __init__(self, config: Config, cli_args: CLIArgs):
        self.config                     = config
        self.cli_args                   = cli_args
        self.failures: List[TestResult] = []

    def log_failures(self):
        log(f"Failure Summary: ({len(self.failures)} tests)")
        for result in self.failures:
            result.log()
            
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
                            test_result: TestResult = tc_runner.run(test, exe)
                            test_result.log() 
                            if test_result.did_pass:
                                sp_pass_count += 1     
                            else:
                                self.failures.append(test_result) 
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
            return self.run_grader_json()
        else:
            return self.run_regular()

    def log_failure_to_file(self, file, result: TestResult):
        """
        Give full feedback to a defender for all the tests they failed
        """
        def trim_bytes(data: bytes, max_bytes: int = 512) -> bytes:
            trimmed = data[:max_bytes]
            if len(data) > max_bytes:
                trimmed += b"\n... (output trimmed to %d bytes)" % max_bytes
            return trimmed

        with open(file, 'a+') as feedback_file:
            if not result.did_pass:
                feedback_file.write(
                    f"Test: {result.test.file}\n"\
                    + "Test contents:\n" + '-'*40 + '\n' + file_to_str(
                                    result.test.path, max_bytes=512) + '\n' + '-'*40 + '\n'\
                    + "Expected Output: " + str(trim_bytes(result.test.expected_out)) + '\n'\
                    + "Generated Output: " + str(trim_bytes(result.gen_output)) + '\n'
                )
                if result.error_msg:
                    feedback_file.write(f"Error Message: {result.error_msg}\n")
                if result.failing_step:
                    feedback_file.write(f"Failing Step: {result.failing_step}\n")
                feedback_file.write("\n")

    @staticmethod
    def create_tc_dataframe(tc_name: str, defenders: List[Executable],
                                          attackers: List[Package]) -> pd.DataFrame:
        """
        Create an empty toolchain table with labels for defenders and attackers 
        """ 
        row_labels = [exe.id for exe in defenders]
        col_labels = [pkg.name for pkg in attackers]
        df = pd.DataFrame(index=row_labels, columns=col_labels) 
        df.index.name = tc_name
        return df
    
    @staticmethod
    def create_timing_dataframe() -> pd.DataFrame:
        """
        TODO: Creating timing DF for Gazprea II
        """
        return pd.DataFrame()

    def run_grader_json(self) -> bool:
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        Write each toolchain table to the CSV file as it's completed.
        """ 
        attacking_pkgs = sorted(self.config.packages, key=lambda pkg: pkg.name.lower())
        defending_exes = sorted(self.config.executables, key=lambda exe: exe.id.lower())
        solution_exe = self.config.solution_exe 

        with open(self.cli_args.failure_log, 'w') as sol_fail_log, \
            open(self.cli_args.grade_file, 'w') as grade_csv:
            
            for toolchain in self.config.toolchains:
                tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
                tc_table = self.create_tc_dataframe(toolchain.name, defending_exes, attacking_pkgs) 
                print(f"\nToolchain: {toolchain.name}")
                
                for def_exe in defending_exes: 
                    def_feedback_file = f"{def_exe.id}-{toolchain.name}feedback.txt"
                    
                    for a_pkg in attacking_pkgs:  
                        pass_count = 0
                        test_count = a_pkg.n_tests
                        print(f"\n  {a_pkg.name:<12} --> {def_exe.id:<12}", end='')
                        
                        for a_spkg in a_pkg.subpackages:
                            for test in a_spkg.tests:
                                test_result: TestResult = tc_runner.run(test, def_exe)

                                if test_result.did_pass:
                                    print(Fore.GREEN + '.' + Fore.RESET, end='')
                                    pass_count += 1 
                                else:      
                                    print(Fore.RED + '.' + Fore.RESET, end='')
                                    self.log_failure_to_file(def_feedback_file, test_result)
                                    if solution_exe == def_exe.id:
                                        sol_fail_log.write(f"{toolchain.name} {a_pkg.name} {test.path}\n")
                        tc_table.at[def_exe.id, a_pkg.name] = f"{pass_count}/{test_count}"
                
                # write the completed toolchain table to the CSV file
                grade_csv.write('\n') 
                tc_table.to_csv(grade_csv)
                grade_csv.flush()

        return True 
