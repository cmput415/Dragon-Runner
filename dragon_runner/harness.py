import json
from colorama               import Fore
from typing                 import List
from dragon_runner.cli      import CLIArgs
from dragon_runner.config   import Config
from dragon_runner.log      import log, log_delimiter
from dragon_runner.testfile import TestFile
from dragon_runner.runner   import TestResult, ToolChainRunner

class TestHarness:
    __test__ = False 
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
                            test_result: TestResult = tc_runner.run(test, exe)
                            test_result.log() 
                            if test_result.did_pass:
                                sp_pass_count += 1     
                            else:
                                self.failures.append(test) 
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

    def run_grader_json(self):
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        For now emit JSON to work with the existing grader script.
        TODO: Make the entire grading process self-contained here.
        """ 
        log("Running in grade mode")

        attacking_pkgs = sorted(self.config.packages, key=lambda pkg: pkg.name.lower())
        defending_exes = sorted(self.config.executables, key=lambda exe: exe.id.lower())

        with open(self.cli_args.failure_log, 'w') as fail_log:
            
            results_json = [] 
            for toolchain in self.config.toolchains:
                tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
                tc_json = {"toolchain": toolchain.name, "toolchainResults": []}
                print(f"Toolchain: {toolchain.name}")
                for def_exe in defending_exes: 
                    def_json = {"defender": def_exe.id, "defenderResults": []}
                    with open(f"{def_exe.id}-{toolchain.name}feedback.txt", 'w') as def_f:
                        for a_pkg in attacking_pkgs:
                            a_json = {
                                "attacker": a_pkg.name,
                                "testCount": a_pkg.n_tests,
                                "timings": []
                            }
                            result_string = ""
                            pass_count = 0
                            for a_spkg in a_pkg.subpackages:
                                for test in a_spkg.tests:
                                    result_json = {"test": test.file}
                                    test_result: TestResult = tc_runner.run(test, def_exe)
                                    if test_result.did_pass:
                                        result_string += Fore.GREEN + '.' + Fore.RESET
                                        result_json.update({"pass": True, "time": test_result.time})
                                        pass_count += 1
                                    if not test_result.did_pass:      
                                        result_string += Fore.RED + '.' + Fore.RESET
                                        result_json.update({"pass": False})
                                        def_f.write(f"Test Failed: {test.file}\n")                                    
                                    a_json["timings"].append(result_json)
                            a_json.update({"passCount": pass_count})
                            print(f"  {a_pkg.name:<12} --> {def_exe.id:<12} {result_string}")
                            def_json["defenderResults"].append(a_json)
                    tc_json["toolchainResults"].append(def_json)
                results_json.append(tc_json)
                print("")
            
        grade_dict = {
            "title": "415 Grades",
            "testSummary": {
                "executables": [exe.id for exe in defending_exes],
                "packages": [{"name": pkg.name, "count": pkg.n_tests} for pkg in attacking_pkgs]
            },
            "results": results_json
        }

        grade_json = json.dumps(grade_dict, indent=2)
        with open(self.cli_args.grade_file, 'w') as grade_f:
            grade_f.write(grade_json)
