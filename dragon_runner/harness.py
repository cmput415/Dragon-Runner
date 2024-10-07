import json
from colorama               import Fore
from typing                 import List
from pathlib                import Path
from dragon_runner.cli      import CLIArgs
from dragon_runner.config   import Config
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
        with open(file, 'a+') as feedback_file:
            if not result.did_pass:
                feedback_file.write(
                    f"Test: {result.test.file}\n"\
                    + "Test contents:\n" + '-'*40 + '\n' + file_to_str(result.test.path, max_bytes=256) + '\n' + '-'*40 + '\n'\
                    + "Expected Output: " + str(result.test.expected_out.getvalue()) + '\n'\
                    + "Generated Output: " + str(result.gen_output) + '\n'
                )
                if result.error_msg:
                    feedback_file.write(f"Error Message: {result.error_msg}\n")
                if result.failing_step:
                    feedback_file.write(f"Failing Step: {result.failing_step}\n")
                feedback_file.write("\n")

    def checkpointed(self, check, checkpoint_data, index, key):
        if self.cli_args.restore and (check == checkpoint_data[index][key]):
            try:
                checkpoint_data[index + 1]
                return True
            except IndexError:
                return False

    def run_grader_json(self) -> bool:
        """
        Run the tester in grade mode. Run all test packages for each tested executable.
        For now emit JSON to work with the existing grader script.
        TODO: Make the entire grading process self-contained here.
        """ 
        log("Running in grade mode")

        attacking_pkgs = sorted(self.config.packages, key=lambda pkg: pkg.name.lower())
        defending_exes = sorted(self.config.executables, key=lambda exe: exe.id.lower())
        solution_exe =  self.config.solution_exe
        checkpoint_path = Path('.checkpoint.json')
        
        with open(self.cli_args.failure_log, 'w') as sol_fail_log:     
            results_json = []

            # If we are restoring from a checkpoint, load it
            if (self.cli_args.restore):
                with open(checkpoint_path, 'r') as checkpoint:
                    checkpoint_restore_raw = checkpoint.read()
                    checkpoint_restore_parsed = json.loads(checkpoint_restore_raw)

                results_json = checkpoint_restore_parsed

            # Run the toolchains
            for i, toolchain in enumerate(self.config.toolchains):
                # Check if we have this toolchain checkpointed
                if self.checkpointed(toolchain.name, results_json, i, 'toolchain'):
                    continue

                tc_runner = ToolChainRunner(toolchain, self.cli_args.timeout)
                tc_json = {"toolchain": toolchain.name, "toolchainResults": []}
                print(f"Toolchain: {toolchain.name}")
                for j, def_exe in enumerate(defending_exes):
                    # Check if we have this defender checkpointed
                    if self.checkpointed(def_exe.id, results_json[i]['toolchainResults'], j, 'defender'):
                        continue

                    def_json = {"defender": def_exe.id, "defenderResults": []}
                    def_feedback_file = f"{def_exe.id}-{toolchain.name}feedback.txt"
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
                                test: TestFile = test 
                                result_json = {"test": test.file}
                                test_result: TestResult = tc_runner.run(test, def_exe)
                                if test_result.did_pass:
                                    result_string += Fore.GREEN + '.' + Fore.RESET
                                    result_json.update({"pass": True, "time": test_result.time})
                                    pass_count += 1
                                if not test_result.did_pass:      
                                    result_string += Fore.RED + '.' + Fore.RESET
                                    result_json.update({"pass": False})
                                    self.log_failure_to_file(def_feedback_file, test_result)
                                    if solution_exe == def_exe.id:
                                        sol_fail_log.write(f"{toolchain.name} {a_pkg.name} {test.path}\n")
                                a_json["timings"].append(result_json)
                        a_json.update({"passCount": pass_count})
                        print(f"  {a_pkg.name:<12} --> {def_exe.id:<12} {result_string}")
                        def_json["defenderResults"].append(a_json)

                        # Set the tmp toolchain json
                        checkpoint_tc = tc_json
                        checkpoint_tc["toolchainResults"].append(def_json)

                        # Set up a checkpoint
                        checkpoint = results_json
                        checkpoint.append(checkpoint_tc)
                        tmp_json = json.dumps(checkpoint)
                        with open(checkpoint_path, 'w') as tmp:
                            tmp.write(tmp_json)

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

        checkpoint_path.unlink(missing_ok=True)

        return True
