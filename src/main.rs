use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::path::Path;

use colored::Colorize;
use dragon_runner_rs::cli::{parse_cli_args, CliAction::*, Mode, RunnerArgs};
use dragon_runner_rs::config::{load_config, Config};
use dragon_runner_rs::grading::{
    average_tables, compute_perf_scores, compute_scores, load_grading_config, write_perf_csv,
    write_perf_summary_csv, write_summary_csv, write_tournament_csv, GradingConfig,
};
use dragon_runner_rs::harness::*;
use dragon_runner_rs::script::run_script;
use dragon_runner_rs::server;
use dragon_runner_rs::{debug, error};

fn main() {
    let action = parse_cli_args();
    let cli_args = match action {
        Script(args) => std::process::exit(run_script(args)),
        Serve {
            config_file,
            bind,
            timeout,
            max_concurrent,
            allow_origin,
        } => {
            let config = load_or_exit(&config_file, None);
            let rt = match tokio::runtime::Runtime::new() {
                Ok(rt) => rt,
                Err(e) => {
                    error!(0, "failed to create tokio runtime: {e}");
                    std::process::exit(1);
                }
            };
            if let Err(e) =
                rt.block_on(server::run_server(config, &bind, timeout, max_concurrent, &allow_origin))
            {
                error!(0, "server error: {e}");
                std::process::exit(1);
            }
            return;
        }
        Run(args) => args,
    };

    debug!(0, "{:?}", cli_args);
    let config = load_or_exit(&cli_args.config_file, Some(&cli_args));
    config.log_test_info();

    let success = match cli_args.mode {
        Mode::Regular => RegularHarness::new().run(&config, &cli_args),
        Mode::Memcheck => MemoryCheckHarness::new().run(&config, &cli_args),
        Mode::Tournament => run_tournament(&config, &cli_args),
        Mode::Perf => run_perf(&config, &cli_args),
    };

    std::process::exit(if success { 0 } else { 1 });
}

fn load_or_exit(path: &Path, args: Option<&RunnerArgs>) -> Config {
    match load_config(path, args) {
        Ok(c) => c,
        Err(errors) => {
            error!(0, "Found Config {} error(s):", errors.len());
            error!(0, "Parsed {} below:", path.display());
            for e in &errors {
                error!(0, "{}", format!("{e}").red());
            }
            std::process::exit(1);
        }
    }
}

/// Load `--grade-config` if given, else defaults. Aborts the process on parse error.
fn resolve_grading_config(cli_args: &RunnerArgs) -> GradingConfig {
    match cli_args.grade_config.as_deref() {
        None => GradingConfig::default(),
        Some(path) => match load_grading_config(path) {
            Ok(c) => c,
            Err(e) => {
                error!(0, "{}", format!("grade config error: {e}").red());
                std::process::exit(1);
            }
        },
    }
}

/// Slugify a config-supplied ID for safe use as a filename component.
/// Anything outside [A-Za-z0-9._-] becomes `_`, and empty or pure-dot
/// results are replaced with `_` so we can't emit `.`, `..`, or hidden files.
fn slugify(s: &str) -> String {
    let cleaned: String = s
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '-' | '_') {
                c
            } else {
                '_'
            }
        })
        .collect();
    if cleaned.is_empty() {
        "_".into()
    } else {
        cleaned
    }
}

fn run_tournament(config: &Config, cli_args: &RunnerArgs) -> bool {
    let Some(output) = TournamentHarness::new().run(config, cli_args) else {
        return false;
    };
    let grading_cfg = resolve_grading_config(cli_args);
    let out_dir = std::path::PathBuf::from(".");

    for table in &output.tables {
        let path = out_dir.join(format!("toolchain_{}.csv", slugify(&table.toolchain)));
        if let Err(e) = write_tournament_csv(table, &path) {
            error!(0, "failed to write {}: {e}", path.display());
            return false;
        }
    }

    if !output.tables.is_empty() {
        let avg = match average_tables(&output.tables) {
            Ok(t) => t,
            Err(e) => {
                error!(0, "{e}");
                return false;
            }
        };
        let solution = cli_args.solution_exe.as_deref().unwrap();
        let scores = match compute_scores(&avg, &grading_cfg, solution) {
            Ok(s) => s,
            Err(e) => {
                error!(0, "{e}");
                return false;
            }
        };
        let summary_path = out_dir.join("summary.csv");
        if let Err(e) = write_summary_csv(&avg, &scores, &grading_cfg, &summary_path) {
            error!(0, "failed to write {}: {e}", summary_path.display());
            return false;
        }
    }

    if let Err(e) = write_feedback_files(&output.failures, &out_dir) {
        error!(0, "failed to write feedback files: {e}");
        return false;
    }

    if let Some(fail_log_path) = &cli_args.failure_log {
        if let Err(e) = write_solution_logs(&output.solution_results, fail_log_path, &out_dir) {
            error!(0, "failed to write solution logs: {e}");
            return false;
        }
    }

    true
}

fn run_perf(config: &Config, cli_args: &RunnerArgs) -> bool {
    let mut harness = PerformanceTestingHarness::new();
    harness.run(config, cli_args);
    let table = harness.into_table();
    let out_dir = std::path::PathBuf::from(".");

    let perf_path = out_dir.join("perf.csv");
    if let Err(e) = write_perf_csv(&table, &perf_path) {
        error!(0, "failed to write {}: {e}", perf_path.display());
        return false;
    }

    let scores = compute_perf_scores(&table);
    let summary_path = out_dir.join("perf_summary.csv");
    if let Err(e) = write_perf_summary_csv(&scores, &summary_path) {
        error!(0, "failed to write {}: {e}", summary_path.display());
        return false;
    }

    true
}

/// Group failures by (defender, toolchain) and write `<defender>-<toolchain>feedback.txt`.
/// Preserves the historical filename shape (`TA-LLVMfeedback.txt`, etc).
fn write_feedback_files(failures: &[TournamentFailure], out_dir: &Path) -> std::io::Result<()> {
    let mut grouped: HashMap<(String, String), Vec<&TournamentFailure>> = HashMap::new();
    for f in failures {
        grouped
            .entry((f.defender.clone(), f.toolchain.clone()))
            .or_default()
            .push(f);
    }
    for ((defender, toolchain), items) in &grouped {
        let path = out_dir.join(format!(
            "{}-{}feedback.txt",
            slugify(defender),
            slugify(toolchain)
        ));
        let mut f = fs::File::create(&path)?;
        for item in items {
            writeln!(
                f,
                "{}\nTest: {}\n\nExpected Output: {:?}\nGenerated Output: {:?}",
                "=".repeat(80),
                item.test_file,
                String::from_utf8_lossy(&item.expected_out),
                String::from_utf8_lossy(&item.generated_out),
            )?;
        }
    }
    Ok(())
}

/// Write solution results in the legacy log format.
fn write_solution_logs(
    results: &[TournamentSolutionResult],
    failure_log: &Path,
    out_dir: &Path,
) -> std::io::Result<()> {
    let pass_path = out_dir.join("pass_log.txt");
    // Truncate pass_log so it stays in sync with the freshly written CSVs;
    // failure_log is user-named and stays in append mode.
    let mut pass = fs::File::create(&pass_path)?;
    let mut fail = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(failure_log)?;
    for r in results {
        let line = format!("{} {} {}", r.toolchain, r.attacker, r.test_path.display());
        if r.did_pass {
            writeln!(pass, "{line}")?;
        } else {
            writeln!(fail, "{line}")?;
        }
    }
    Ok(())
}
