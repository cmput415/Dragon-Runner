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
        self.config = config
        self.cli_args: CLIArgs = cli_args
        self.failures: List[TestResult] = []

    def log_failures(self):
        """Report failures to stdout."""
        log("Failure Log:") 
        for result in self.failures:
            result.log()

    def process_test_result(self, test_result: Optional[TestResult], counters: Dict[str, int]):
        """
        Process each test result.
        Subclasses should override this method to handle test result processing and update counts.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def pre_subpackage_hook(self, spkg):
        """Hook for actions before iterating through a subpackage."""
        pass

    def post_subpackage_hook(self, counters: Dict[str, int]):
        """Hook for actions after iterating through a subpackage."""
        pass

    def iterate(self):
        for exe in self.config.executables:
            log("Running executable:\t", exe.id, indent=0)
            exe.source_env()
            exe_pass_count = 0
            exe_test_count = 0
            for toolchain in self.config.toolchains:
                tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
                log("Running Toolchain:\t", toolchain.name, indent=1)
                tc_pass_count = 0
                tc_test_count = 0
                for pkg in self.config.packages:
                    pkg_pass_count = 0
                    pkg_test_count = 0
                    log(f"Entering package {pkg.name}", indent=2)
                    for spkg in pkg.subpackages:
                        log(f"Entering subpackage {spkg.name}", indent=3)
                        counters = {"pass_count": 0, "test_count": 0}
                        self.pre_subpackage_hook(spkg)
                        for test in spkg.tests:
                            test_result: Optional[TestResult] = tc_runner.run(test, exe)
                            self.process_test_result(test_result, counters)
                        self.post_subpackage_hook(counters)
                        log("Subpackage Passed: ", counters["pass_count"], "/", counters["test_count"], indent=3)
                        pkg_pass_count += counters["pass_count"]
                        pkg_test_count += counters["test_count"]
                    log("Packaged Passed: ", pkg_pass_count, "/", pkg_test_count, indent=2)
                    tc_pass_count += pkg_pass_count
                    tc_test_count += pkg_test_count
                log("Toolchain Passed: ", tc_pass_count, "/", tc_test_count, indent=1)
                exe_pass_count += tc_pass_count
                exe_test_count += tc_test_count
            log("Executable Passed: ", exe_pass_count, "/", exe_test_count)

    def run(self) -> bool:
        """Default run implementation."""
        try:
            self.iterate()
        except Exception as e:
            log("Error during iteration:", e)
            return False
        return len(self.failures) == 0

class RegularHarness(TestHarness):
     
    def process_test_result(self, test_result: Optional[TestResult], counters: Dict[str, int]):
        """
        Override the hook for regular run-specific implementation of counting passes
        """
        if not test_result:
            log("Failed to receive test result")
        elif test_result.did_pass:
            counters["pass_count"] += 1
            test_result.log(args=self.cli_args)
        else:
            self.failures.append(test_result)
            test_result.log(args=self.cli_args)
        counters["test_count"] += 1

class TournamentHarness(TestHarness):

    def process_test_result(self,
            test_result: Optional[TestResult],
            counters: Dict[str, int],
            context: Dict[str, str]
        ):
        """
        Override the hook for grading specifics.
        """
        def_feedback_file = context["def_feedback_file"]
        solution_exe = context["solution_exe"]
        failure_log = context["failure_log"]
        toolchain_name = context["toolchain_name"]
        a_pkg_name = context["a_pkg_name"]

        if not test_result:
            log(f"Failed to run test {test.stem}")
            context["exit_status"] = False
        elif test_result.did_pass:
            print(Fore.GREEN + '.' + Fore.RESET, end='')
            counters['pass_count'] += 1
        else:
            print(Fore.RED + '.' + Fore.RESET, end='')
            self.log_failure_to_file(def_feedback_file, test_result)
            if solution_exe == context["def_exe_id"] and failure_log:
                with open(failure_log, 'a') as f_log:
                    f_log.write(f"{toolchain_name} {a_pkg_name} {test_result.test.path}\n")

    def iterate(self) -> bool:
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        Write each toolchain table to the CSV file as it's completed.
        """
        attacking_pkgs = sorted(self.config.packages, key=lambda pkg: pkg.name.lower())
        defending_exes = sorted(self.config.executables, key=lambda exe: exe.id.lower())
        solution_exe = self.config.solution_exe
        failure_log = self.cli_args.failure_log
        exit_status = 1

        for toolchain in self.config.toolchains:
            tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
            tc_table = self.create_tc_dataframe(defending_exes, attacking_pkgs)

            with open(f"toolchain_{toolchain.name}.csv", 'w') as toolchain_csv:
                print(f"\nToolchain: {toolchain.name}")
                csv_writer = csv.writer(toolchain_csv)
                for def_exe in defending_exes:
                    def_exe.source_env()
                    def_feedback_file = f"{def_exe.id}-{toolchain.name}feedback.txt"
                    for a_pkg in attacking_pkgs:
                        counters = {"pass_count": 0, "test_count": a_pkg.n_tests}
                        print(f"\n  {a_pkg.name:<12} --> {def_exe.id:<12}", end='')

                        context = {
                            "def_feedback_file": def_feedback_file,
                            "solution_exe": solution_exe,
                            "failure_log": failure_log,
                            "toolchain_name": toolchain.name,
                            "a_pkg_name": a_pkg.name,
                            "def_exe_id": def_exe.id,
                            "exit_status": exit_status,
                        }

                        for a_spkg in a_pkg.subpackages:
                            for test in a_spkg.tests:
                                test_result: Optional[TestResult] = tc_runner.run(test, def_exe)
                                self.process_test_result(test_result, counters, context)

                        cell_value = f"{counters['pass_count']} / {counters['test_count']}"
                        tc_table[def_exe.id][a_pkg.name] = cell_value

                # write the toolchain results into the table
                csv_writer.writerow([toolchain.name] + [pkg.name for pkg in attacking_pkgs])
                for exe in defending_exes:
                    csv_writer.writerow([exe.id] + [tc_table[exe.id][pkg.name] for pkg in attacking_pkgs])

        return context["exit_status"]

    @staticmethod
    def create_tc_dataframe(defenders: List[Executable],
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

    def log_failure_to_file(self, file, result: TestResult):
        """
        Give full feedback to a defender for all the tests they failed.
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

class MemoryCheckHarness(TestHarness):
    
    def process_test_result(self, test_result: Optional[TestResult], counters: Dict[str, int]):
        """
        Override the hook for regular run-specific implementation of counting passes
        """
        if not test_result:
            log("Failed to receive test result")
        elif test_result.did_pass:
            counters["pass_count"] += 1
            test_result.log(args=self.cli_args)
        else:
            self.failures.append(test_result)
            test_result.log(args=self.cli_args)
        counters["test_count"] += 1

class PerformanceTestingHarness(TestHarness):
    
    def process_test_result(self, test_result: Optional[TestResult], counters: Dict[str, int]):
        """
        Override the hook for regular run-specific implementation of counting passes
        """
        if not test_result:
            log("Failed to receive test result")
        elif test_result.did_pass:
            counters["pass_count"] += 1
            test_result.log(args=self.cli_args)
        else:
            self.failures.append(test_result)
            test_result.log(args=self.cli_args)
        counters["test_count"] += 1
  
