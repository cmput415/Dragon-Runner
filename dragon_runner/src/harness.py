import csv
from colorama                   import Fore
from typing                     import Any, List, Dict, Optional, Set, Tuple
from dragon_runner.src.cli      import RunnerArgs
from dragon_runner.src.config   import Config, Executable, Package
from dragon_runner.src.log      import log
from dragon_runner.src.runner   import TestResult, ToolChainRunner
from dragon_runner.src.utils    import file_to_str
from itertools                  import zip_longest
from concurrent.futures         import ThreadPoolExecutor, as_completed
import threading
import uuid
from queue import Queue
from dataclasses import dataclass

@dataclass
class SubpackageResult:
    subpackage: Any
    test_results: List[Tuple[int, TestResult]]
    counters: Dict[str, int]

@dataclass
class PackageResult:
    package_index: int
    package: Package
    subpackage_results: List[SubpackageResult]
    pass_count: int
    test_count: int

class TestHarness:
    __test__ = False

    def __init__(self, config: Config, cli_args: RunnerArgs):
        self.config = config
        self.cli_args: RunnerArgs = cli_args
        self.failures: List[TestResult] = []
        self.run_passed = True

    def process_test_result(self, test_result: TestResult, context: Dict[str, Any]):
        """
        Subclasses should override this method to handle test result processing and update counts.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def pre_subpackage_hook(self, spkg):
        """Hook to run before iterating through a subpackage."""
        pass

    def post_subpackage_hook(self, context: Dict[str, Any]):
        """Hook to run after iterating through a subpackage."""
        pass

    def pre_executable_hook(self, exe):
        """Hook to run efore iterating through an executable."""
        pass

    def post_executable_hook(self):
        """Hook to run after iterating through an executable"""
        if self.failures != []:
            log(f"Failure Summary: ({len(self.failures)} tests)")
            for result in self.failures:
                result.log()
        self.failures = []

    def post_run_hook(self):
        pass

    def pre_run_hook(self):
        pass

    def run_test_parallel(self, test, toolchain, timeout, exe, test_index):
        """
        Run a single test and return the result with its original index for ordering.
        Creates a new ToolChainRunner instance to ensure thread safety.
        """
        # Create a new ToolChainRunner instance for each thread to ensure thread safety
        tc_runner = ToolChainRunner(toolchain, timeout)
        test_result = tc_runner.run(test, exe)
        return (test_index, test_result)

    def run_package_parallel(self, package, package_index, toolchain, timeout, exe, tests_per_package_workers):
        """
        Run a single package and return the result with its original index for ordering.
        Creates a new ToolChainRunner instance to ensure thread safety.
        """
        subpackage_results = []
        pkg_pass_count = 0
        pkg_test_count = 0

        for spkg in package.subpackages:
            counters = {"pass_count": 0, "test_count": 0}

            # Execute tests in parallel within this subpackage
            test_results = self.execute_tests_parallel(
                spkg.tests, toolchain, timeout, exe,
                max_workers=tests_per_package_workers
            )

            # Process test results for this subpackage
            for test_index, test_result in test_results:
                # Update counters based on test result
                if test_result.did_pass:
                    counters["pass_count"] += 1
                counters["test_count"] += 1

            subpackage_results.append(SubpackageResult(
                subpackage=spkg,
                test_results=test_results,
                counters=counters
            ))

            pkg_pass_count += counters["pass_count"]
            pkg_test_count += counters["test_count"]

        return PackageResult(
            package_index=package_index,
            package=package,
            subpackage_results=subpackage_results,
            pass_count=pkg_pass_count,
            test_count=pkg_test_count
        )

    def execute_tests_parallel(self, tests, toolchain, timeout, exe, max_workers=1):
        """
        Execute tests in parallel while preserving order using an output queue.
        """
        if max_workers == 1:
            # Sequential execution for single worker
            tc_runner = ToolChainRunner(toolchain, timeout)
            results = []
            for i, test in enumerate(tests):
                test_result = tc_runner.run(test, exe)
                results.append((i, test_result))
            return results

        # Parallel execution for multiple workers
        results = [None] * len(tests)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all test jobs
            future_to_index = {
                executor.submit(self.run_test_parallel, test, toolchain, timeout, exe, i): i
                for i, test in enumerate(tests)
            }

            # Collect results and preserve order
            for future in as_completed(future_to_index):
                test_index, test_result = future.result()
                results[test_index] = test_result

        # Convert to list of tuples for compatibility
        return [(i, result) for i, result in enumerate(results)]

    def execute_packages_parallel(self, packages, toolchain, timeout, exe, max_workers=1):
        """
        Execute test packages in parallel while preserving order using an output queue.
        """
        if max_workers == 1:
            # Sequential execution for single worker - process packages one by one
            package_results = []
            for i, package in enumerate(packages):
                pkg_result = self.run_package_parallel(
                    package, i, toolchain, timeout, exe, tests_per_package_workers=1
                )
                package_results.append(pkg_result)
            return package_results

        # Calculate thread allocation for package vs test parallelization
        num_packages = len(packages)
        package_workers = min(num_packages, max_workers)
        tests_per_package_workers = max(1, max_workers // package_workers)

        # Parallel execution for multiple workers
        results = [None] * len(packages)

        with ThreadPoolExecutor(max_workers=package_workers) as executor:
            # Submit all package jobs
            future_to_index = {
                executor.submit(self.run_package_parallel, package, i, toolchain, timeout, exe, tests_per_package_workers): i
                for i, package in enumerate(packages)
            }

            # Collect results and preserve order
            for future in as_completed(future_to_index):
                package_result = future.result()
                results[package_result.package_index] = package_result

        return results

    def process_package_result(self, pkg_result: PackageResult, tc_pass_count: int, tc_test_count: int):
        """
        Process a package result sequentially to maintain clean logging and hook execution.
        Returns updated (tc_pass_count, tc_test_count) tuple.
        """
        pkg_pass_count = 0
        pkg_test_count = 0
        log(f"Entering package {pkg_result.package.name}", indent=2)

        for spkg_result in pkg_result.subpackage_results:
            log(f"Entering subpackage {spkg_result.subpackage.name}", indent=3)
            self.pre_subpackage_hook(spkg_result.subpackage)

            # Process test results in original order
            for test_index, test_result in spkg_result.test_results:
                self.process_test_result(test_result, spkg_result.counters)
                if self.cli_args.fast_fail and not test_result.did_pass:
                    self.post_subpackage_hook(spkg_result.counters)
                    self.post_executable_hook()
                    self.post_run_hook()
                    return tc_pass_count, tc_test_count, True  # Signal fast fail

            self.post_subpackage_hook(spkg_result.counters)
            log("Subpackage Passed: ", spkg_result.counters["pass_count"], "/", spkg_result.counters["test_count"], indent=3)
            pkg_pass_count += spkg_result.counters["pass_count"]
            pkg_test_count += spkg_result.counters["test_count"]

        log("Packaged Passed: ", pkg_pass_count, "/", pkg_test_count, indent=2)
        tc_pass_count += pkg_pass_count
        tc_test_count += pkg_test_count

        return tc_pass_count, tc_test_count, False  # No fast fail

    def iterate(self):
        """
        Basic structure to record which tests pass and fail. Additional functionality
        can be implemented by overriding default hooks.
        """
        self.pre_run_hook()
        for exe in self.config.executables:
            self.pre_executable_hook(exe.id)
            log(f"Running executable: {exe.id}", indent=0)
            exe.source_env()
            exe_pass_count = 0
            exe_test_count = 0
            for toolchain in self.config.toolchains:
                log(f"Running Toolchain: {toolchain.name}", indent=1)
                tc_pass_count = 0
                tc_test_count = 0

                # Execute packages in parallel if jobs > 1, otherwise sequentially
                package_results = self.execute_packages_parallel(
                    self.config.packages, toolchain, self.cli_args.timeout, exe,
                    max_workers=self.cli_args.jobs
                )

                # Process results sequentially to maintain clean logging
                for pkg_result in package_results:
                    tc_pass_count, tc_test_count, should_fast_fail = self.process_package_result(
                        pkg_result, tc_pass_count, tc_test_count
                    )
                    if should_fast_fail:
                        return
                log("Toolchain Passed: ", tc_pass_count, "/", tc_test_count, indent=1)
                exe_pass_count += tc_pass_count
                exe_test_count += tc_test_count
            log("Executable Passed: ", exe_pass_count, "/", exe_test_count)
            self.post_executable_hook()
        self.post_run_hook()

    def run(self):
        """Default run implementation."""
        self.iterate()
        return self.run_passed

class RegularHarness(TestHarness):

    def process_test_result(self, test_result: TestResult, context: Dict[str, Any]):
        """
        Override the hook for regular run-specific implementation of counting passes
        """
        if test_result.did_pass:
            context["pass_count"] += 1
            test_result.log(args=self.cli_args)
        else:
            self.run_passed = False
            self.failures.append(test_result)
            test_result.log(args=self.cli_args)
        context["test_count"] += 1

class TournamentHarness(TestHarness):

    def iterate(self):
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        Write each toolchain table to the CSV file as it's completed.
        """
        attacking_pkgs = sorted(self.config.packages, key=lambda pkg: pkg.name.lower())
        defending_exes = sorted(self.config.executables, key=lambda exe: exe.id.lower())
        solution_exe = self.config.solution_exe
        failure_log = self.cli_args.failure_log

        for toolchain in self.config.toolchains:
            tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
            tc_table = self.create_tc_dataframe(defending_exes, attacking_pkgs)

            with open(f"toolchain_{toolchain.name}.csv", 'w') as toolchain_csv:
                print(f"\nToolchain: {toolchain.name}")
                csv_writer = csv.writer(toolchain_csv)
                csv_writer.writerow([toolchain.name] + [pkg.name for pkg in attacking_pkgs])
                toolchain_csv.flush()

                for def_exe in defending_exes:
                    def_exe.source_env()
                    def_feedback_file = f"{def_exe.id}-{toolchain.name}feedback.txt"
                    for a_pkg in attacking_pkgs:
                        print(f"\n  {a_pkg.name:<12} --> {def_exe.id:<12}", end='')
                        pass_count = 0
                        test_count = 0
                        for a_spkg in a_pkg.subpackages:
                            # Execute tests in parallel for tournament mode
                            test_results = self.execute_tests_parallel(
                                a_spkg.tests, toolchain, self.cli_args.timeout, def_exe, max_workers=self.cli_args.jobs
                            )

                            # Process results in original order
                            for test_index, test_result in test_results:
                                if test_result and test_result.did_pass:
                                    print(Fore.GREEN + '.' + Fore.RESET, end='')
                                    pass_count += 1
                                    if solution_exe == def_exe.id and failure_log:
                                        with open("pass_log.txt", 'a') as f_log:
                                            f_log.write(f"{toolchain.name} {a_pkg.name} {test_result.test.path}\n")
                                else:
                                    print(Fore.RED + '.' + Fore.RESET, end='')
                                    self.log_failure_to_file(def_feedback_file, test_result)
                                    if solution_exe == def_exe.id and failure_log:
                                        with open(failure_log, 'a') as f_log:
                                            f_log.write(f"{toolchain.name} {a_pkg.name} {test_result.test.path}\n")
                                test_count += 1

                        cell_value = f"{pass_count}/{test_count}"
                        tc_table[def_exe.id][a_pkg.name] = cell_value
                    csv_writer.writerow([def_exe.id] + [tc_table[def_exe.id][pkg.name] for pkg in attacking_pkgs])
                    toolchain_csv.flush()

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
                feedback_string = (
                  "="*80+'\n'
                  f"Test: {result.test.file}\n"
                  f"\nTest Contents: {test_contents.strip() if test_contents else ''}\n"
                  f"\nExpected Output: {exp_out.strip()}\n"
                  f"\nGenerated Output: {gen_out.strip()}\n"
                )

                feedback_file.write(feedback_string)

class MemoryCheckHarness(TestHarness):

    def __init__(self, config: Config, cli_args: RunnerArgs):
        super().__init__(config, cli_args)
        self.leak_count = 0
        self.test_count = 0
        self.leak_tests: List[TestResult] = []

    def post_executable_hook(self):
        """
        Report failures to stdout.
        """
        log(f"Leak Summary: ({len(self.leak_tests)} tests)")
        for result in self.leak_tests:
            log(Fore.YELLOW + "[LEAK] " + Fore.RESET + f"{result.test.file}",
                indent=4)
        self.leak_tests = []
        self.test_count = 0 # reset for each executable

        if self.failures != []:
            log(f"Failure Summary: ({len(self.failures)} tests)")
            for result in self.failures:
                result.log()

    def process_test_result(self, test_result: TestResult, context: Dict[str, Any]):
        """
        Override the hook for regular run-specific implementation of counting passes
        """
        # TODO: Refactor an clean up. Not simple enough

        # increment the test count
        self.test_count += 1
        context["test_count"] += 1

        # log the test result
        test_result.log(args=self.cli_args)

        # track tests which leak
        if test_result.memory_leak:
            self.leak_tests.append(test_result)

        # track passes as usual
        if test_result.did_pass:
            context["pass_count"] += 1
        else:
            self.failures.append(test_result)

class PerformanceTestingHarness(TestHarness):

    def __init__(self, config: Config, cli_args: RunnerArgs):
        super().__init__(config, cli_args)
        self.csv_cols = []
        self.cur_col = []
        self.testfile_col = ["Test"]
        self.first_exec = True

    @staticmethod
    def create_tc_dataframe(defenders: List[Executable],
                            attackers: List[Package]) -> Dict[str, Set[str]]:
        """
        Create an empty toolchain table with labels for defenders and attackers
        """
        df = {exe.id: {pkg.name for pkg in attackers} for exe in defenders}
        return df

    def process_test_result(self, test_result: TestResult, context: Dict[str, Any]):
        """
        Override the hook for regular run-specific implementation of counting passes
        """
        # only construct a column for the test file names once
        if self.first_exec:
            self.testfile_col.append(test_result.test.file)

        if test_result.did_pass:
            context["pass_count"] += 1
            test_result.log(args=self.cli_args)
            self.cur_col.append(test_result.time)

        else:
            self.cur_col.append(self.cli_args.timeout)
            self.failures.append(test_result)
            test_result.log(args=self.cli_args)
        context["test_count"] += 1

    def pre_executable_hook(self, exe):
        self.cur_col.append(exe)

    def post_executable_hook(self):
        if self.first_exec:
            self.csv_cols.append(self.testfile_col)
            self.first_exec = False

        self.csv_cols.append(self.cur_col)
        self.cur_col = []

    def post_run_hook(self):
        # transpose the columns into rows for writing
        csv_rows = zip_longest(*self.csv_cols, fillvalue='')

        with open('perf.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(csv_rows)

