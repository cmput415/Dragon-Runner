use std::fs;

use colored::Colorize;
use rayon::prelude::*;

use crate::cli::{Mode, RunnerArgs};
use crate::config::{Config, Executable, Package};
use crate::grading::{PerfTable, TournamentTable};
use crate::info;
use crate::log::log;
use crate::progress;
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

/// Format a timing suffix for the PASS/FAIL line.
/// Matches Python: right-aligned in a 10-char field followed by ` (s)`.
fn time_suffix(result: &TestResult, show_time: bool) -> String {
    if show_time {
        if let Some(t) = result.time {
            return format!("{:>10.4} (s)", t);
        }
    }
    String::new()
}

/// Truncate bytes with middle omission if they exceed `max_bytes`.
/// Matches Python's `truncated_bytes()`.
fn truncated_bytes(data: &[u8], max_bytes: usize) -> Vec<u8> {
    if data.len() <= max_bytes {
        return data.to_vec();
    }
    let omission = b"\n{{ omitted for brevity }}\n";
    let available = max_bytes.saturating_sub(omission.len());
    let half = available / 2;
    let mut out = Vec::with_capacity(max_bytes);
    out.extend_from_slice(&data[..half]);
    out.extend_from_slice(omission);
    out.extend_from_slice(&data[data.len() - half..]);
    out
}

/// Generate a pretty-printed box around file contents.
/// Matches Python's `TestFile.pretty_print()`.
fn pretty_print_file(path: &std::path::Path) -> Option<String> {
    let content = fs::read_to_string(path).ok()?;
    let term_width = terminal_size::terminal_size()
        .map(|(w, _)| w.0 as usize)
        .unwrap_or(80);
    let content_width = std::cmp::min(term_width.saturating_sub(10), 100);
    if content_width < 6 {
        return Some(content);
    }

    let mut lines = Vec::new();
    // top border
    lines.push(format!(
        "\u{250c}{}\u{2510}",
        "\u{2500}".repeat(content_width - 2)
    ));
    for line in content.lines() {
        let display = if line.len() > content_width - 4 {
            format!("{}...", &line[..content_width - 7])
        } else {
            line.to_string()
        };
        lines.push(format!(
            "\u{2502} {:<width$} \u{2502}",
            display,
            width = content_width - 4
        ));
    }
    // bottom border
    lines.push(format!(
        "\u{2514}{}\u{2518}",
        "\u{2500}".repeat(content_width - 2)
    ));
    Some(lines.join("\n"))
}

/// Print additional test details below the PASS/FAIL line based on CLI flags.
/// Called by both RegularHarness and MemoryCheckHarness.
/// Matches the Python `TestResult.log()` output order and verbosity levels.
fn print_test_details(result: &TestResult, cli_args: &RunnerArgs, indent: usize) {
    // -s: show testcase (level 0 on fail, level 2 on pass)
    if cli_args.show_testcase {
        let level: u32 = if result.did_pass { 2 } else { 0 };
        if let Some(boxed) = pretty_print_file(&result.test.path) {
            for line in boxed.lines() {
                log(level, indent + 2, format_args!("{line}"));
            }
        }
    }

    // Command history: level 3 on pass, level 2 on fail
    let cmd_level: u32 = if result.did_pass { 3 } else { 2 };
    log(cmd_level, indent + 2, format_args!("==> Command History"));
    for cr in &result.command_history {
        log(
            cmd_level,
            indent + 4,
            format_args!("==> {} (exit {})", cr.cmd, cr.exit_status),
        );
        let stdout = truncated_bytes(&cr.stdout, 512);
        log(
            cmd_level,
            indent + 6,
            format_args!(
                "stdout ({} bytes): {}",
                cr.stdout.len(),
                String::from_utf8_lossy(&stdout),
            ),
        );
        let stderr = truncated_bytes(&cr.stderr, 512);
        log(
            cmd_level,
            indent + 6,
            format_args!(
                "stderr ({} bytes): {}",
                cr.stderr.len(),
                String::from_utf8_lossy(&stderr),
            ),
        );
    }

    // Expected vs Generated output: level 2 on pass, level 1 on fail
    let diff_level: u32 = if result.did_pass { 2 } else { 1 };
    let expected_out = result.test.get_expected_out();
    let generated_out = result.gen_output.as_deref().unwrap_or(b"");
    log(
        diff_level,
        indent + 2,
        format_args!("==> Expected Out ({} bytes):", expected_out.len()),
    );
    log(diff_level, indent + 3, format_args!("{:?}", expected_out));
    log(
        diff_level,
        indent + 2,
        format_args!("==> Generated Out ({} bytes):", generated_out.len()),
    );
    log(diff_level, indent + 3, format_args!("{:?}", generated_out));
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
    fn process_test_result(
        &mut self,
        result: TestResult,
        cli_args: &RunnerArgs,
        counters: &mut SubPackageCounters,
    );
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
                        let mut counters = SubPackageCounters {
                            pass_count: 0,
                            test_count: 0,
                            skip_count: 0,
                            depth: spkg.depth,
                        };
                        self.pre_subpackage_hook(spkg);

                        let results: Vec<TestResult> = spkg
                            .tests
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
                        info!(
                            3 + spkg.depth,
                            "Subpackage Passed:  {} / {}{}",
                            counters.pass_count,
                            counters.test_count,
                            skip_suffix(counters.skip_count)
                        );
                        pkg_pass += counters.pass_count;
                        pkg_total += counters.test_count;
                        pkg_skip += counters.skip_count;
                    }

                    info!(
                        2,
                        "Packaged Passed:  {} / {}{}",
                        pkg_pass,
                        pkg_total,
                        skip_suffix(pkg_skip)
                    );
                    tc_pass += pkg_pass;
                    tc_total += pkg_total;
                    tc_skip += pkg_skip;
                }

                info!(
                    1,
                    "Toolchain Passed:  {} / {}{}",
                    tc_pass,
                    tc_total,
                    skip_suffix(tc_skip)
                );
                exe_pass += tc_pass;
                exe_total += tc_total;
                exe_skip += tc_skip;
            }

            info!(
                0,
                "Executable Passed:  {} / {}{}",
                exe_pass,
                exe_total,
                skip_suffix(exe_skip)
            );
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
    fn run_passed(&self) -> bool {
        self.passed
    }

    fn process_test_result(
        &mut self,
        result: TestResult,
        cli_args: &RunnerArgs,
        counters: &mut SubPackageCounters,
    ) {
        let indent = 4 + counters.depth;
        let test_name = test_display_name(&result.test, cli_args.full_path);
        if result.skipped {
            info!(indent, "{}{}", "[SKIP] ".yellow(), test_name);
            counters.skip_count += 1;
            return;
        }
        let time = time_suffix(&result, cli_args.time);
        if result.did_pass {
            let tag = if result.error_test {
                "[E-PASS] "
            } else {
                "[PASS] "
            };
            info!(indent, "{}{}{}", tag.green(), test_name, time);
            counters.pass_count += 1;
        } else {
            let tag = if result.error_test {
                "[E-FAIL] "
            } else {
                "[FAIL] "
            };
            info!(indent, "{}{}{}", tag.red(), test_name, time);
            self.passed = false;
        }
        counters.test_count += 1;
        print_test_details(&result, cli_args, indent);
    }
}

// ---------------------------------------------------------------------------
// TournamentHarness
// ---------------------------------------------------------------------------

/// A failing test recorded during tournament iteration, kept only well enough
/// to reconstruct feedback files.
pub struct TournamentFailure {
    pub toolchain: String,
    pub defender: String,
    pub test_file: String,
    pub expected_out: Vec<u8>,
    pub generated_out: Vec<u8>,
}

/// A test the *solution* executable passed. Emitted alongside failures so
/// `--fail-log` can produce both `pass_log.txt` and the fail log.
pub struct TournamentSolutionResult {
    pub toolchain: String,
    pub attacker: String,
    pub test_path: std::path::PathBuf,
    pub did_pass: bool,
}

/// Full result of a tournament run. Owns everything needed to compute grades
/// or write per-team feedback files; no I/O happens inside the harness.
pub struct TournamentOutput {
    pub tables: Vec<TournamentTable>,
    pub failures: Vec<TournamentFailure>,
    pub solution_results: Vec<TournamentSolutionResult>,
}

pub struct TournamentHarness;

impl TournamentHarness {
    pub fn new() -> Self {
        Self
    }

    /// Run the cross-product tournament and return everything needed to
    /// write CSVs and feedback files. All output paths are the caller's
    /// responsibility.
    ///
    /// Returns `None` if the tournament could not run (missing `--solution-exe`
    /// or the id doesn't match any executable). The error is printed to stderr.
    pub fn run(&self, config: &Config, cli_args: &RunnerArgs) -> Option<TournamentOutput> {
        let Some(solution_exe) = cli_args.solution_exe.as_deref() else {
            crate::error!(0, "Error: --solution-exe is required in tournament mode");
            return None;
        };
        if !config.executables.iter().any(|e| e.id == solution_exe) {
            crate::error!(0, "Error: --solution-exe '{}' does not match any executable in the config.\nAvailable: {:?}",
                solution_exe, config.executables.iter().map(|e| &e.id).collect::<Vec<_>>());
            return None;
        }

        let mut attacking_pkgs: Vec<&Package> = config.packages.iter().collect();
        attacking_pkgs.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));

        let mut defending_exes: Vec<&Executable> = config.executables.iter().collect();
        defending_exes.sort_by(|a, b| a.id.to_lowercase().cmp(&b.id.to_lowercase()));

        let mut tables = Vec::with_capacity(config.toolchains.len());
        let mut failures = Vec::new();
        let mut solution_results = Vec::new();

        for tc in &config.toolchains {
            info!(0, "\nToolchain: {}", tc.name);
            let mut cells = vec![vec![(0u32, 0u32); attacking_pkgs.len()]; defending_exes.len()];

            for (i, def_exe) in defending_exes.iter().enumerate() {
                let runner =
                    ToolChainRunner::new(tc, cli_args.timeout).with_env(def_exe.runtime_env());
                let is_solution = solution_exe == def_exe.id;

                for (j, a_pkg) in attacking_pkgs.iter().enumerate() {
                    progress!("\n  {:<12} --> {:<12}", a_pkg.name, def_exe.id);
                    let mut pass_count = 0u32;
                    let mut test_count = 0u32;

                    for test in a_pkg.subpackages.iter().flat_map(|s| &s.tests) {
                        let result = runner.run(test, def_exe);
                        if result.skipped {
                            progress!("{}", ".".yellow());
                            continue;
                        }
                        test_count += 1;

                        if result.did_pass {
                            progress!("{}", ".".green());
                            pass_count += 1;
                        } else {
                            progress!("{}", ".".red());
                            failures.push(TournamentFailure {
                                toolchain: tc.name.clone(),
                                defender: def_exe.id.clone(),
                                test_file: result.test.file.clone(),
                                expected_out: result.test.get_expected_out().to_vec(),
                                generated_out: result.gen_output.clone().unwrap_or_default(),
                            });
                        }

                        if is_solution {
                            solution_results.push(TournamentSolutionResult {
                                toolchain: tc.name.clone(),
                                attacker: a_pkg.name.clone(),
                                test_path: result.test.path.clone(),
                                did_pass: result.did_pass,
                            });
                        }
                    }

                    cells[i][j] = (pass_count, test_count);
                }
            }

            tables.push(TournamentTable {
                toolchain: tc.name.clone(),
                defenders: defending_exes.iter().map(|e| e.id.clone()).collect(),
                attackers: attacking_pkgs.iter().map(|p| p.name.clone()).collect(),
                cells,
            });
        }

        Some(TournamentOutput {
            tables,
            failures,
            solution_results,
        })
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
        Self {
            passed: true,
            leak_tests: Vec::new(),
            test_count: 0,
        }
    }
}

impl SequentialTestHarness for MemoryCheckHarness {
    fn run_passed(&self) -> bool {
        self.passed
    }

    fn process_test_result(
        &mut self,
        result: TestResult,
        cli_args: &RunnerArgs,
        counters: &mut SubPackageCounters,
    ) {
        let indent = 4 + counters.depth;
        let test_name = test_display_name(&result.test, cli_args.full_path);
        if result.skipped {
            info!(indent, "{}{}", "[SKIP] ".yellow(), test_name);
            counters.skip_count += 1;
            return;
        }
        self.test_count += 1;
        counters.test_count += 1;

        let time = time_suffix(&result, cli_args.time);
        if result.did_pass {
            info!(indent, "{}{}{}", "[PASS] ".green(), test_name, time);
            counters.pass_count += 1;
        } else {
            info!(indent, "{}{}{}", "[FAIL] ".red(), test_name, time);
        }

        print_test_details(&result, cli_args, indent);

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

/// Collects per-(test, executable) timings; returns a `PerfTable` for the
/// caller to grade and write.
pub struct PerformanceTestingHarness {
    /// Timings by executable, in the order executables are encountered. Each
    /// inner Vec is a column: one entry per test (in `tests` order).
    columns: Vec<Vec<f64>>,
    tests: Vec<String>,
    exe_ids: Vec<String>,
    current_column: Vec<f64>,
    first_exec: bool,
}

impl PerformanceTestingHarness {
    pub fn new() -> Self {
        Self {
            columns: Vec::new(),
            tests: Vec::new(),
            exe_ids: Vec::new(),
            current_column: Vec::new(),
            first_exec: true,
        }
    }

    /// Assemble a `PerfTable`. `times_seconds[test][compiler]`.
    pub fn into_table(self) -> PerfTable {
        let num_tests = self.tests.len();
        let num_compilers = self.exe_ids.len();
        let mut times = vec![vec![0.0f64; num_compilers]; num_tests];
        for (c, col) in self.columns.iter().enumerate() {
            for (r, &t) in col.iter().enumerate() {
                if r < num_tests {
                    times[r][c] = t;
                }
            }
        }
        PerfTable {
            compilers: self.exe_ids,
            tests: self.tests,
            times_seconds: times,
        }
    }
}

impl SequentialTestHarness for PerformanceTestingHarness {
    fn run_passed(&self) -> bool {
        true
    }

    fn process_test_result(
        &mut self,
        result: TestResult,
        cli_args: &RunnerArgs,
        counters: &mut SubPackageCounters,
    ) {
        let indent = 4 + counters.depth;
        let test_name = test_display_name(&result.test, cli_args.full_path);
        if result.skipped {
            info!(indent, "{}{}", "[SKIP] ".yellow(), test_name);
            counters.skip_count += 1;
            return;
        }
        if self.first_exec {
            self.tests.push(result.test.file.clone());
        }

        if result.did_pass {
            counters.pass_count += 1;
            info!(indent, "{}{}", "[PASS] ".green(), test_name);
            self.current_column
                .push(result.time.unwrap_or(cli_args.timeout));
        } else {
            self.current_column.push(cli_args.timeout);
        }
        counters.test_count += 1;
    }

    fn pre_executable_hook(&mut self, exe_id: &str) {
        self.exe_ids.push(exe_id.into());
        self.current_column.clear();
    }

    fn post_executable_hook(&mut self) {
        self.columns.push(std::mem::take(&mut self.current_column));
        self.first_exec = false;
    }
}
