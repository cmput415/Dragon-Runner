use dragon_runner_rs::cli::{parse_cli_args, CliAction::*, Mode, RunnerArgs};
use dragon_runner_rs::config::{load_or_exit, Config};
use dragon_runner_rs::grading::{
    average_tables, compute_perf_scores, compute_scores, resolve_grading_config, write_perf_csv,
    write_perf_summary_csv, write_summary_csv, write_tournament_csv,
};
use dragon_runner_rs::harness::*;
use dragon_runner_rs::script::run_script;
use dragon_runner_rs::server;
use dragon_runner_rs::util::slugify;
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
