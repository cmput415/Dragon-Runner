use std::fs::{self, OpenOptions};
use std::io::Write;

use colored::Colorize;
use rayon::prelude::*;

use crate::info;
use crate::cli::{Mode, RunnerArgs};
use crate::config::{Config, Executable, Package};
use crate::runner::{TestResult, ToolChainRunner};
use crate::testfile::TestFile;

/// Format a skip count suffix for summary lines.
fn skip_suffix(skip_count: usize) -> String {
    if skip_count > 0 {
        format!(" ({skip_count} skipped)")
    } else {
        String::new()
    }
}

/// Returns the full path or just the filename depending on the flag.
fn test_display_name(test: &TestFile, full_path: bool) -> String {
    if full_path {
        test.path.display().to_string()
    } else {
        test.file.clone()
    }
}

/// Counters passed through hooks during iteration.
pub struct SubPackageCounters {
    pub pass_count: usize,
    pub test_count: usize,
    pub skip_count: usize,
    pub depth: usize,
}

/// Implemented by any `TestHarness` which makes a single, sequential iteration
/// over the tests in each package and subpackage. Applies to all except for
/// the `TournamentHarness`, which iterates in a cross product.
pub trait SequentialTestHarness {

    fn run_passed(&self) -> bool;
    fn process_test_result(&mut self, result: TestResult, cli_args: &RunnerArgs, counters: &mut SubPackageCounters);
    fn pre_run_hook(&mut self) {}
    fn post_run_hook(&mut self) {}
    fn pre_executable_hook(&mut self, _exe_id: &str) {}
    fn post_executable_hook(&mut self) {}
    fn pre_subpackage_hook(&mut self, _spkg: &crate::config::SubPackage) {}
    fn post_subpackage_hook(&mut self, _counters: &SubPackageCounters) {}

    /// Default iteration: executables x toolchains x packages x subpackages x tests.
    fn iterate(&mut self, config: &Config, cli_args: &RunnerArgs) {
        self.pre_run_hook();

        let filter_pat = if config.package_filter.is_empty() {
            None
        } else {
            glob::Pattern::new(&config.package_filter.to_lowercase()).ok()
        };

        for exe in &config.executables {
            self.pre_executable_hook(&exe.id);
            info!(0, "Running executable: {}", exe.id);
            let exe_env = exe.runtime_env();
            let mut exe_pass = 0;
            let mut exe_total = 0;
            let mut exe_skip = 0;

            for tc in &config.toolchains {
                let runner = ToolChainRunner::new(tc, cli_args.timeout)
                    .with_env(exe_env.clone())
                    .with_memcheck(cli_args.mode == Mode::Memcheck);
                info!(1, "Running Toolchain: {}", tc.name);
                let mut tc_pass = 0;
                let mut tc_total = 0;
                let mut tc_skip = 0;

                for pkg in &config.packages {
                    let mut pkg_pass = 0;
                    let mut pkg_total = 0;
                    let mut pkg_skip = 0;
                    info!(2, "Entering package {}", pkg.name);

                    for spkg in &pkg.subpackages {
                        if let Some(ref pat) = filter_pat {
                            if !pat.matches(&spkg.path.display().to_string().to_lowercase()) {
                                continue;
                            }
                        }

                        info!(3 + spkg.depth, "Entering subpackage {}", spkg.name);
                        let mut counters = SubPackageCounters { pass_count: 0, test_count: 0, skip_count: 0, depth: spkg.depth };
                        self.pre_subpackage_hook(spkg);

                        let results: Vec<TestResult> = spkg.tests
                            .par_iter()
                            .map(|test| runner.run(test, exe))
                            .collect();

                        for result in results {
                            let fast_fail = cli_args.fast_fail && !result.did_pass;
                            self.process_test_result(result, cli_args, &mut counters);
                            if fast_fail {
                                self.post_subpackage_hook(&counters);
                                self.post_executable_hook();
                                self.post_run_hook();
                                return;
                            }
                        }

                        self.post_subpackage_hook(&counters);
                        info!(3 + spkg.depth, "Subpackage Passed:  {} / {}{}", counters.pass_count, counters.test_count, skip_suffix(counters.skip_count));
                        pkg_pass += counters.pass_count;
                        pkg_total += counters.test_count;
                        pkg_skip += counters.skip_count;
                    }

                    info!(2, "Packaged Passed:  {} / {}{}", pkg_pass, pkg_total, skip_suffix(pkg_skip));
                    tc_pass += pkg_pass;
                    tc_total += pkg_total;
                    tc_skip += pkg_skip;
                }

                info!(1, "Toolchain Passed:  {} / {}{}", tc_pass, tc_total, skip_suffix(tc_skip));
                exe_pass += tc_pass;
                exe_total += tc_total;
                exe_skip += tc_skip;
            }

            info!(0, "Executable Passed:  {} / {}{}", exe_pass, exe_total, skip_suffix(exe_skip));
            self.post_executable_hook();
        }

        self.post_run_hook();
    }

    fn run(&mut self, config: &Config, cli_args: &RunnerArgs) -> bool {
        self.iterate(config, cli_args);
        self.run_passed()
    }
}

// ---------------------------------------------------------------------------
// RegularHarness
// ---------------------------------------------------------------------------

pub struct RegularHarness {
    pub passed: bool,
}

impl RegularHarness {
    pub fn new() -> Self {
        Self { passed: true }
    }
}

impl SequentialTestHarness for RegularHarness {
    fn run_passed(&self) -> bool { self.passed }

    fn process_test_result(&mut self, result: TestResult, cli_args: &RunnerArgs, counters: &mut SubPackageCounters) {
        let indent = 4 + counters.depth;
        let test_name = test_display_name(&result.test, cli_args.full_path);
        if result.skipped {
            info!(indent, "{}{}", "[SKIP] ".yellow(), test_name);
            counters.skip_count += 1;
            return;
        }
        if result.did_pass {
            let tag = if result.error_test { "[E-PASS] " } else { "[PASS] " };
            info!(indent, "{}{}", tag.green(), test_name);
            counters.pass_count += 1;
        } else {
            let tag = if result.error_test { "[E-FAIL] " } else { "[FAIL] " };
            info!(indent, "{}{}", tag.red(), test_name);
            self.passed = false;
        }
        counters.test_count += 1;
    }
}

// ---------------------------------------------------------------------------
// TournamentHarness
// ---------------------------------------------------------------------------

pub struct TournamentHarness {
    pub passed: bool,
}

impl TournamentHarness {
    pub fn new() -> Self {
        Self { passed: true }
    }

    /// Tournament has its own iteration logic (cross-product of packages x executables).
    pub fn run(&mut self, config: &Config, cli_args: &RunnerArgs) -> bool {
        self.tournament_iterate(config, cli_args);
        self.passed
    }

    fn log_failure_to_file(file: &str, result: &TestResult) {
        if result.did_pass {
            return;
        }
        let Ok(mut f) = OpenOptions::new().create(true).append(true).open(file) else { return };

        let exp = String::from_utf8_lossy(result.test.get_expected_out());
        let gen = result.gen_output.as_deref()
            .map(|b| String::from_utf8_lossy(b).into_owned())
            .unwrap_or_default();

        let _ = writeln!(f, "{}\nTest: {}\n\nExpected Output: {exp:?}\nGenerated Output: {gen:?}",
            "=".repeat(80), result.test.file);
    }

    fn append_log(path: &std::path::Path, line: &str) {
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(f, "{line}");
        }
    }

    fn tournament_iterate(&mut self, config: &Config, cli_args: &RunnerArgs) {
        let mut attacking_pkgs: Vec<&Package> = config.packages.iter().collect();
        attacking_pkgs.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));

        let mut defending_exes: Vec<&Executable> = config.executables.iter().collect();
        defending_exes.sort_by(|a, b| a.id.to_lowercase().cmp(&b.id.to_lowercase()));

        let solution_exe = config.solution_exe.as_deref();
        let failure_log = cli_args.failure_log.as_deref();

        for tc in &config.toolchains {
            let csv_filename = format!("toolchain_{}.csv", tc.name);
            let mut csv_file = fs::File::create(&csv_filename).expect("cannot create CSV");

            let header: Vec<&str> = std::iter::once(tc.name.as_str())
                .chain(attacking_pkgs.iter().map(|p| p.name.as_str()))
                .collect();
            let _ = writeln!(csv_file, "{}", header.join(","));
            println!("\nToolchain: {}", tc.name);

            for def_exe in &defending_exes {
                let runner = ToolChainRunner::new(tc, cli_args.timeout)
                    .with_env(def_exe.runtime_env());
                let feedback_file = format!("{}-{}feedback.txt", def_exe.id, tc.name);
                let mut row_cells: Vec<String> = vec![def_exe.id.clone()];

                for a_pkg in &attacking_pkgs {
                    print!("\n  {:<12} --> {:<12}", a_pkg.name, def_exe.id);
                    let mut pass_count = 0usize;
                    let mut test_count = 0usize;

                    let tests = a_pkg.subpackages.iter().flat_map(|s| &s.tests);
                    for test in tests {
                        let result = runner.run(test, def_exe);
                        if result.skipped {
                            print!("{}", ".".yellow());
                            continue;
                        }
                        let is_solution = solution_exe == Some(&def_exe.id);

                        if result.did_pass {
                            print!("{}", ".".green());
                            pass_count += 1;
                            if is_solution && failure_log.is_some() {
                                Self::append_log("pass_log.txt".as_ref(), &format!(
                                    "{} {} {}", tc.name, a_pkg.name, result.test.path.display()
                                ));
                            }
                        } else {
                            print!("{}", ".".red());
                            Self::log_failure_to_file(&feedback_file, &result);
                            if let Some(log) = failure_log {
                                if is_solution {
                                    Self::append_log(log, &format!(
                                        "{} {} {}", tc.name, a_pkg.name, result.test.path.display()
                                    ));
                                }
                            }
                        }
                        test_count += 1;
                    }

                    row_cells.push(format!("{pass_count}/{test_count}"));
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
    pub passed: bool,
    pub leak_tests: Vec<TestResult>,
    pub test_count: usize,
}

impl MemoryCheckHarness {
    pub fn new() -> Self {
        Self { passed: true, leak_tests: Vec::new(), test_count: 0 }
    }
}

impl SequentialTestHarness for MemoryCheckHarness {
    fn run_passed(&self) -> bool { self.passed }

    fn process_test_result(&mut self, result: TestResult, cli_args: &RunnerArgs, counters: &mut SubPackageCounters) {
        let indent = 4 + counters.depth;
        let test_name = test_display_name(&result.test, cli_args.full_path);
        if result.skipped {
            info!(indent, "{}{}", "[SKIP] ".yellow(), test_name);
            counters.skip_count += 1;
            return;
        }
        self.test_count += 1;
        counters.test_count += 1;

        if result.did_pass {
            info!(indent, "{}{}", "[PASS] ".green(), test_name);
            counters.pass_count += 1;
        } else {
            info!(indent, "{}{}", "[FAIL] ".red(), test_name);
        }

        if result.memory_leak {
            self.leak_tests.push(result);
        }
    }

    fn post_executable_hook(&mut self) {
        info!(0, "Leak Summary: ({} tests)", self.leak_tests.len());
        for result in &self.leak_tests {
            info!(4, "{}{}", "[LEAK] ".yellow(), result.test.file);
        }
        self.leak_tests.clear();
        self.test_count = 0;
    }
}

// ---------------------------------------------------------------------------
// PerformanceTestingHarness
// ---------------------------------------------------------------------------

pub struct PerformanceTestingHarness {
    pub passed: bool,
    pub csv_cols: Vec<Vec<String>>,
    pub cur_col: Vec<String>,
    pub testfile_col: Vec<String>,
    pub first_exec: bool,
}

impl PerformanceTestingHarness {
    pub fn new() -> Self {
        Self {
            passed: true,
            csv_cols: Vec::new(),
            cur_col: Vec::new(),
            testfile_col: vec!["Test".into()],
            first_exec: true,
        }
    }
}

impl SequentialTestHarness for PerformanceTestingHarness {
    fn run_passed(&self) -> bool { self.passed }

    fn process_test_result(&mut self, result: TestResult, cli_args: &RunnerArgs, counters: &mut SubPackageCounters) {
        let indent = 4 + counters.depth;
        let test_name = test_display_name(&result.test, cli_args.full_path);
        if result.skipped {
            info!(indent, "{}{}", "[SKIP] ".yellow(), test_name);
            counters.skip_count += 1;
            return;
        }
        if self.first_exec {
            self.testfile_col.push(result.test.file.clone());
        }

        if result.did_pass {
            counters.pass_count += 1;
            info!(indent, "{}{}", "[PASS] ".green(), test_name);
            self.cur_col.push(result.time.map(|t| format!("{t:.4}")).unwrap_or_default());
        } else {
            self.cur_col.push(format!("{:.4}", cli_args.timeout));
        }
        counters.test_count += 1;
    }

    fn pre_executable_hook(&mut self, exe_id: &str) {
        self.cur_col.push(exe_id.into());
    }

    fn post_executable_hook(&mut self) {
        if self.first_exec {
            self.csv_cols.push(self.testfile_col.clone());
            self.first_exec = false;
        }
        self.csv_cols.push(std::mem::take(&mut self.cur_col));
    }

    fn post_run_hook(&mut self) {
        let max_len = self.csv_cols.iter().map(|c| c.len()).max().unwrap_or(0);
        let mut f = fs::File::create("perf.csv").expect("cannot create perf.csv");
        for row_idx in 0..max_len {
            let row: Vec<&str> = self.csv_cols.iter()
                .map(|col| col.get(row_idx).map(|s| s.as_str()).unwrap_or(""))
                .collect();
            let _ = writeln!(f, "{}", row.join(","));
        }
    }
}

#[cfg(test)]
mod tests {
    use std::path::{Path, PathBuf};

    use crate::cli::{Mode, RunnerArgs};
    use crate::config::load_config;
    use super::TournamentHarness;

    fn config_path(name: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests").join("configs").join(name)
    }

    #[test]
    fn test_grader_config() {
        let path = config_path("ConfigGrade.json");
        let config = load_config(&path, None).expect("config should load");

        let failure_log = Path::new("Failures_rs.txt");
        let _ = std::fs::remove_file(failure_log);

        let args = RunnerArgs {
            mode: Mode::Tournament,
            failure_log: Some(failure_log.into()),
            timeout: 2.0,
            ..Default::default()
        };

        let mut harness = TournamentHarness::new();
        harness.run(&config, &args);

        assert!(
            failure_log.exists(),
            "failure log should have been created"
        );

        let _ = std::fs::remove_file(failure_log);
    }
}
