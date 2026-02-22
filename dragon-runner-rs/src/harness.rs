use std::fs::{self, OpenOptions};
use std::io::Write;

use colored::Colorize;

use crate::cli::RunnerArgs;
use crate::config::{Config, Executable, Package};
use crate::log::log;
use crate::runner::{TestResult, ToolChainRunner};

/// Counters passed through hooks during iteration.
pub struct SubPackageCounters {
    pub pass_count: usize,
    pub test_count: usize,
}

/// Base harness logic — iterate over executables, toolchains, packages, subpackages, tests.
/// Concrete harnesses implement the hooks.
pub trait TestHarness {
    fn config(&self) -> &Config;
    fn cli_args(&self) -> &RunnerArgs;
    fn run_passed(&self) -> bool;
    fn set_run_passed(&mut self, val: bool);

    fn process_test_result(&mut self, result: TestResult, counters: &mut SubPackageCounters);

    fn pre_run_hook(&mut self) {}
    fn post_run_hook(&mut self) {}
    fn pre_executable_hook(&mut self, _exe_id: &str) {}
    fn post_executable_hook(&mut self) {}
    fn pre_subpackage_hook(&mut self, _spkg: &crate::config::SubPackage) {}
    fn post_subpackage_hook(&mut self, _counters: &SubPackageCounters) {}

    fn iterate(&mut self) {
        self.pre_run_hook();

        let config = self.config().clone();
        let cli_args = self.cli_args().clone();

        for exe in &config.executables {
            self.pre_executable_hook(&exe.id);
            log(0, 0, &format!("Running executable: {}", exe.id));
            exe.source_env();
            let mut exe_pass = 0;
            let mut exe_total = 0;

            for tc in &config.toolchains {
                let runner = ToolChainRunner::new(tc.clone(), cli_args.timeout);
                log(0, 1, &format!("Running Toolchain: {}", tc.name));
                let mut tc_pass = 0;
                let mut tc_total = 0;

                for pkg in &config.packages {
                    let mut pkg_pass = 0;
                    let mut pkg_total = 0;
                    log(0, 2, &format!("Entering package {}", pkg.name));

                    for spkg in &pkg.subpackages {
                        // Glob filter
                        if !config.package_filter.is_empty() {
                            let pat = glob::Pattern::new(&config.package_filter.to_lowercase());
                            if let Ok(pat) = pat {
                                if !pat.matches(&spkg.path.to_lowercase()) {
                                    continue;
                                }
                            }
                        }

                        log(0, 3, &format!("Entering subpackage {}", spkg.name));
                        let mut counters = SubPackageCounters {
                            pass_count: 0,
                            test_count: 0,
                        };
                        self.pre_subpackage_hook(spkg);

                        for test in &spkg.tests {
                            let result = runner.run(test, exe);
                            let fast_fail = cli_args.fast_fail && !result.did_pass;
                            self.process_test_result(result, &mut counters);
                            if fast_fail {
                                self.post_subpackage_hook(&counters);
                                self.post_executable_hook();
                                self.post_run_hook();
                                return;
                            }
                        }

                        self.post_subpackage_hook(&counters);
                        log(
                            0,
                            3,
                            &format!(
                                "Subpackage Passed:  {} / {}",
                                counters.pass_count, counters.test_count
                            ),
                        );
                        pkg_pass += counters.pass_count;
                        pkg_total += counters.test_count;
                    }

                    log(0, 2, &format!("Packaged Passed:  {} / {}", pkg_pass, pkg_total));
                    tc_pass += pkg_pass;
                    tc_total += pkg_total;
                }

                log(0, 1, &format!("Toolchain Passed:  {} / {}", tc_pass, tc_total));
                exe_pass += tc_pass;
                exe_total += tc_total;
            }

            log(0, 0, &format!("Executable Passed:  {} / {}", exe_pass, exe_total));
            self.post_executable_hook();
        }

        self.post_run_hook();
    }

    fn run(&mut self) -> bool {
        self.iterate();
        self.run_passed()
    }
}

// ---------------------------------------------------------------------------
// RegularHarness
// ---------------------------------------------------------------------------

pub struct RegularHarness {
    pub config: Config,
    pub cli_args: RunnerArgs,
    pub failures: Vec<TestResult>,
    pub passed: bool,
}

impl RegularHarness {
    pub fn new(config: Config, cli_args: RunnerArgs) -> Self {
        Self {
            config,
            cli_args,
            failures: Vec::new(),
            passed: true,
        }
    }
}

impl TestHarness for RegularHarness {
    fn config(&self) -> &Config { &self.config }
    fn cli_args(&self) -> &RunnerArgs { &self.cli_args }
    fn run_passed(&self) -> bool { self.passed }
    fn set_run_passed(&mut self, val: bool) { self.passed = val; }

    fn process_test_result(&mut self, result: TestResult, counters: &mut SubPackageCounters) {
        let test_name = result.test.file.clone();
        if result.did_pass {
            let tag = if result.error_test { "[E-PASS] " } else { "[PASS] " };
            log(0, 4, &format!("{}{}", tag.green(), test_name));
        } else {
            let tag = if result.error_test { "[E-FAIL] " } else { "[FAIL] " };
            log(0, 4, &format!("{}{}", tag.red(), test_name));
            self.passed = false;
            self.failures.push(result);
        }
        counters.test_count += 1;
        if counters.test_count > 0 && counters.test_count > counters.pass_count {
            // already counted pass below
        }
        // Re-check: pass counting
        counters.pass_count += if self.failures.last().map(|f| f.test.file == test_name).unwrap_or(false) {
            0
        } else {
            // the test we just processed passed
            1
        };
    }

    fn post_executable_hook(&mut self) {
        self.failures.clear();
    }
}

// ---------------------------------------------------------------------------
// TournamentHarness
// ---------------------------------------------------------------------------

pub struct TournamentHarness {
    pub config: Config,
    pub cli_args: RunnerArgs,
    pub passed: bool,
}

impl TournamentHarness {
    pub fn new(config: Config, cli_args: RunnerArgs) -> Self {
        Self {
            config,
            cli_args,
            passed: true,
        }
    }

    fn log_failure_to_file(file: &str, result: &TestResult) {
        if result.did_pass {
            return;
        }
        let mut f = OpenOptions::new()
            .create(true)
            .append(true)
            .open(file)
            .unwrap_or_else(|_| panic!("Cannot open feedback file: {}", file));

        let exp_out = result.test.get_expected_out();
        let gen_out = result.gen_output.as_deref().unwrap_or(b"");

        let _ = writeln!(f, "{}", "=".repeat(80));
        let _ = writeln!(f, "Test: {}", result.test.file);
        let _ = writeln!(f, "\nExpected Output: {:?}", String::from_utf8_lossy(exp_out));
        let _ = writeln!(f, "Generated Output: {:?}", String::from_utf8_lossy(gen_out));
    }
}

impl TestHarness for TournamentHarness {
    fn config(&self) -> &Config { &self.config }
    fn cli_args(&self) -> &RunnerArgs { &self.cli_args }
    fn run_passed(&self) -> bool { self.passed }
    fn set_run_passed(&mut self, val: bool) { self.passed = val; }

    fn process_test_result(&mut self, _result: TestResult, _counters: &mut SubPackageCounters) {
        // Tournament uses its own iterate, this is unused
    }

    fn iterate(&mut self) {
        let config = self.config.clone();
        let cli_args = self.cli_args.clone();

        let mut attacking_pkgs: Vec<&Package> = config.packages.iter().collect();
        attacking_pkgs.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));

        let mut defending_exes: Vec<&Executable> = config.executables.iter().collect();
        defending_exes.sort_by(|a, b| a.id.to_lowercase().cmp(&b.id.to_lowercase()));

        let solution_exe = config.solution_exe.as_deref();
        let failure_log = &cli_args.failure_log;

        for tc in &config.toolchains {
            let runner = ToolChainRunner::new(tc.clone(), cli_args.timeout);

            let csv_filename = format!("toolchain_{}.csv", tc.name);
            let mut csv_file = fs::File::create(&csv_filename).expect("cannot create CSV");

            // Header row
            let header: Vec<&str> = std::iter::once(tc.name.as_str())
                .chain(attacking_pkgs.iter().map(|p| p.name.as_str()))
                .collect();
            let _ = writeln!(csv_file, "{}", header.join(","));

            println!("\nToolchain: {}", tc.name);

            for def_exe in &defending_exes {
                def_exe.source_env();
                let feedback_file = format!("{}-{}feedback.txt", def_exe.id, tc.name);
                let mut row_cells: Vec<String> = vec![def_exe.id.clone()];

                for a_pkg in &attacking_pkgs {
                    print!("\n  {:<12} --> {:<12}", a_pkg.name, def_exe.id);
                    let mut pass_count = 0;
                    let mut test_count = 0;

                    for a_spkg in &a_pkg.subpackages {
                        for test in &a_spkg.tests {
                            let result = runner.run(test, def_exe);
                            if result.did_pass {
                                print!("{}", ".".green());
                                pass_count += 1;
                                if solution_exe == Some(&def_exe.id) && !failure_log.is_empty() {
                                    let mut f = OpenOptions::new()
                                        .create(true)
                                        .append(true)
                                        .open("pass_log.txt")
                                        .ok();
                                    if let Some(ref mut f) = f {
                                        let _ = writeln!(
                                            f,
                                            "{} {} {}",
                                            tc.name, a_pkg.name, result.test.path
                                        );
                                    }
                                }
                            } else {
                                print!("{}", ".".red());
                                Self::log_failure_to_file(&feedback_file, &result);
                                if solution_exe == Some(&def_exe.id) && !failure_log.is_empty() {
                                    let mut f = OpenOptions::new()
                                        .create(true)
                                        .append(true)
                                        .open(failure_log)
                                        .ok();
                                    if let Some(ref mut f) = f {
                                        let _ = writeln!(
                                            f,
                                            "{} {} {}",
                                            tc.name, a_pkg.name, result.test.path
                                        );
                                    }
                                }
                            }
                            test_count += 1;
                        }
                    }

                    row_cells.push(format!("{}/{}", pass_count, test_count));
                }

                let _ = writeln!(csv_file, "{}", row_cells.join(","));
            }
        }
    }
}

// ---------------------------------------------------------------------------
// MemoryCheckHarness
// ---------------------------------------------------------------------------

pub struct MemoryCheckHarness {
    pub config: Config,
    pub cli_args: RunnerArgs,
    pub passed: bool,
    pub leak_tests: Vec<TestResult>,
    pub test_count: usize,
}

impl MemoryCheckHarness {
    pub fn new(config: Config, cli_args: RunnerArgs) -> Self {
        Self {
            config,
            cli_args,
            passed: true,
            leak_tests: Vec::new(),
            test_count: 0,
        }
    }
}

impl TestHarness for MemoryCheckHarness {
    fn config(&self) -> &Config { &self.config }
    fn cli_args(&self) -> &RunnerArgs { &self.cli_args }
    fn run_passed(&self) -> bool { self.passed }
    fn set_run_passed(&mut self, val: bool) { self.passed = val; }

    fn process_test_result(&mut self, result: TestResult, counters: &mut SubPackageCounters) {
        self.test_count += 1;
        counters.test_count += 1;

        let test_name = result.test.file.clone();
        if result.did_pass {
            let tag = "[PASS] ";
            log(0, 4, &format!("{}{}", tag.green(), test_name));
            counters.pass_count += 1;
        } else {
            let tag = "[FAIL] ";
            log(0, 4, &format!("{}{}", tag.red(), test_name));
        }

        if result.memory_leak {
            self.leak_tests.push(result);
        }
    }

    fn post_executable_hook(&mut self) {
        log(0, 0, &format!("Leak Summary: ({} tests)", self.leak_tests.len()));
        for result in &self.leak_tests {
            log(
                0,
                4,
                &format!("{}{}", "[LEAK] ".yellow(), result.test.file),
            );
        }
        self.leak_tests.clear();
        self.test_count = 0;
    }
}

// ---------------------------------------------------------------------------
// PerformanceTestingHarness
// ---------------------------------------------------------------------------

pub struct PerformanceTestingHarness {
    pub config: Config,
    pub cli_args: RunnerArgs,
    pub passed: bool,
    pub csv_cols: Vec<Vec<String>>,
    pub cur_col: Vec<String>,
    pub testfile_col: Vec<String>,
    pub first_exec: bool,
    pub failures: Vec<TestResult>,
}

impl PerformanceTestingHarness {
    pub fn new(config: Config, cli_args: RunnerArgs) -> Self {
        Self {
            config,
            cli_args,
            passed: true,
            csv_cols: Vec::new(),
            cur_col: Vec::new(),
            testfile_col: vec!["Test".to_string()],
            first_exec: true,
            failures: Vec::new(),
        }
    }
}

impl TestHarness for PerformanceTestingHarness {
    fn config(&self) -> &Config { &self.config }
    fn cli_args(&self) -> &RunnerArgs { &self.cli_args }
    fn run_passed(&self) -> bool { self.passed }
    fn set_run_passed(&mut self, val: bool) { self.passed = val; }

    fn process_test_result(&mut self, result: TestResult, counters: &mut SubPackageCounters) {
        if self.first_exec {
            self.testfile_col.push(result.test.file.clone());
        }

        let test_name = result.test.file.clone();
        if result.did_pass {
            counters.pass_count += 1;
            log(0, 4, &format!("{}{}", "[PASS] ".green(), test_name));
            self.cur_col
                .push(result.time.map(|t| format!("{:.4}", t)).unwrap_or_default());
        } else {
            self.cur_col
                .push(format!("{:.4}", self.cli_args.timeout));
            self.failures.push(result);
        }
        counters.test_count += 1;
    }

    fn pre_executable_hook(&mut self, exe_id: &str) {
        self.cur_col.push(exe_id.to_string());
    }

    fn post_executable_hook(&mut self) {
        if self.first_exec {
            self.csv_cols.push(self.testfile_col.clone());
            self.first_exec = false;
        }
        self.csv_cols.push(self.cur_col.clone());
        self.cur_col.clear();
    }

    fn post_run_hook(&mut self) {
        // Transpose columns into rows
        let max_len = self.csv_cols.iter().map(|c| c.len()).max().unwrap_or(0);
        let mut f = fs::File::create("perf.csv").expect("cannot create perf.csv");
        for row_idx in 0..max_len {
            let row: Vec<&str> = self
                .csv_cols
                .iter()
                .map(|col| {
                    col.get(row_idx).map(|s| s.as_str()).unwrap_or("")
                })
                .collect();
            let _ = writeln!(f, "{}", row.join(","));
        }
    }
}
