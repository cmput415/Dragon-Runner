import csv
from colorama               import Fore
from typing                 import List, Dict, Optional
from dragon_runner.cli      import CLIArgs
from dragon_runner.config   import Config, Executable, Package
from dragon_runner.log      import log
from dragon_runner.runner   import TestResult, ToolChainRunner
from dragon_runner.utils    import file_to_str

class TestHarness:
    __test__ = False 
    def __init__(self, config: Config, cli_args: CLIArgs):
        self.config                     = config
        self.cli_args: CLIArgs          = cli_args
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
        success = True
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
                    pkg_pass_count = 0
                    pkg_test_count = 0
                    log(f"Entering package {pkg.name}", indent=1)
                    for spkg in pkg.subpackages:
                        log(f"Entering subpackage {spkg.name}", indent=2)
                        sp_pass_count = 0
                        sp_test_count = 0
                        for test in spkg.tests:
                            test_result: Optional[TestResult] = tc_runner.run(test, exe)
                            if not test_result:
                                success=False
                                log(f"Failed to receive test result for: {test.stem}")
                            elif test_result.did_pass:
                                sp_pass_count += 1     
                                test_result.log(args=self.cli_args)
                            else:
                                self.failures.append(test_result) 
                                test_result.log(args=self.cli_args)
                            sp_test_count +=1 
                        log("Subpackage Passed: ", sp_pass_count, "/", sp_test_count, indent=2)
                        pkg_pass_count += sp_pass_count
                        pkg_test_count += sp_test_count
                    log("Packaged Passed: ", pkg_pass_count, "/", pkg_test_count, indent=1)
                    tc_pass_count += pkg_pass_count
                    tc_test_count += pkg_test_count 
                log("Toolchain Passed: ", tc_pass_count, "/", tc_test_count)
                exe_pass_count += tc_pass_count
                exe_test_count += tc_test_count
            log("Executable Passed: ", exe_pass_count, "/", exe_test_count)
            if exe_pass_count != exe_test_count:
                success = False
        return success

    def run(self) -> bool:
        """
        decide wether to run in regular mode or grade mode based on the CLI args 
        """ 
        if self.cli_args.is_tournament_mode():
            return self.run_tournament()

        elif self.cli_args.is_regular_mode():
            return self.run_regular()

        else:
            return False

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
                test_contents = file_to_str(result.test.path)
                exp_out = trim_bytes(x) if isinstance(x := result.test.expected_out, bytes) else ""
                gen_out = trim_bytes(x) if isinstance(x := result.gen_output, bytes) else ""

                feedback_file.write(
                    f"""Test: {result.test.file}\n
                        Test contents: {test_contents}\n
                        Expected Output: {exp_out}\n
                        Generated Output: {gen_out} 
                    """
                )
                if result.error_msg:
                    feedback_file.write(f"Error Message: {result.error_msg}\n")
                if result.failing_step:
                    feedback_file.write(f"Failing Step: {result.failing_step}\n")
                feedback_file.write("\n")

    @staticmethod
    def create_tc_dataframe(tc_name: str, defenders: List[Executable],
                            attackers: List[Package]) -> Dict[str, Dict[str, str]]:
        """
        Create an empty toolchain table with labels for defenders and attackers 
        """ 
        df = {exe.id: {pkg.name: '' for pkg in attackers} for exe in defenders}
        return df

    @staticmethod
    def create_timing_dataframe() -> Dict[str, Dict[str, float]]:
        """
        TODO: Creating timing DF for Gazprea II (Only applicable for grading)
        """
        return {}

    def run_tournament(self) -> bool:
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        Write each toolchain table to the CSV file as it's completed.
        """ 
        attacking_pkgs = sorted(self.config.packages, key=lambda pkg: pkg.name.lower())
        defending_exes = sorted(self.config.executables, key=lambda exe: exe.id.lower())
        solution_exe = self.config.solution_exe 
        failure_log = self.cli_args.failure_log

        # track grader internal errors
        exit_status = True

        for toolchain in self.config.toolchains:
            tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
            tc_table = self.create_tc_dataframe(toolchain.name, defending_exes, attacking_pkgs)

            with open(f"toolchain_{toolchain.name}.csv", 'w') as toolchain_csv:
                print(f"\nToolchain: {toolchain.name}") 
                csv_writer = csv.writer(toolchain_csv)
                for def_exe in defending_exes: 
                    def_exe.source_env()
                    def_feedback_file = f"{def_exe.id}-{toolchain.name}feedback.txt" 
                    for a_pkg in attacking_pkgs:  
                        pass_count = 0
                        test_count = a_pkg.n_tests
                        print(f"\n  {a_pkg.name:<12} --> {def_exe.id:<12}", end='') 
                        for a_spkg in a_pkg.subpackages:
                            for test in a_spkg.tests:
                                test_result: Optional[TestResult] = tc_runner.run(test, def_exe)
                                if not test_result:
                                    log(f"Failed to run test {test.stem}")
                                    exit_status=False
                                elif test_result.did_pass:
                                    print(Fore.GREEN + '.' + Fore.RESET, end='')
                                    pass_count += 1 
                                else:      
                                    print(Fore.RED + '.' + Fore.RESET, end='')
                                    self.log_failure_to_file(def_feedback_file, test_result)
                                    if solution_exe == def_exe.id and failure_log is not None:
                                        with open(failure_log, 'a') as f_log:
                                            f_log.write(f"{toolchain.name} {a_pkg.name} {test.path}\n")

                        tc_table[def_exe.id][a_pkg.name] = f"{pass_count}/{test_count}"
                
                # write the toolchain results into the table
                csv_writer.writerow([toolchain.name] + [pkg.name for pkg in attacking_pkgs]) 
                for exe in defending_exes:
                    csv_writer.writerow([exe.id] + [tc_table[exe.id][pkg.name] for pkg in attacking_pkgs])

        return exit_status 
