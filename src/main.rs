use colored::Colorize;
use dragon_runner_rs::cli::{parse_cli_args, CliAction, Mode};
use dragon_runner_rs::config::load_config;
use dragon_runner_rs::harness::*;
use dragon_runner_rs::{info, debug};
use dragon_runner_rs::script::run_script;
use dragon_runner_rs::server;

fn main() {
    let action = parse_cli_args();
    let cli_args = match action {
        CliAction::Script(args) => {
            std::process::exit(run_script(args));
        }
        CliAction::Serve { config_file, bind, timeout, max_concurrent } => {
            let config = match load_config(&config_file, None) {
                Some(c) => c,
                None => {
                    info!(0, "Could not open config file: {}", config_file.display());
                    std::process::exit(1);
                }
            };
            if !config.errors.is_empty() {
                info!(0, "Found Config {} error(s):", config.errors.len());
                for e in &config.errors {
                    info!(0, "{}", format!("{e}").red());
                }
                std::process::exit(1);
            }
            let rt = tokio::runtime::Runtime::new().expect("failed to create tokio runtime");
            rt.block_on(server::run_server(config, &bind, timeout, max_concurrent));
            return;
        }
        CliAction::Run(args) => args,
    };

    debug!(0, "{:?}", cli_args);
    let config = match load_config(&cli_args.config_file, Some(&cli_args)) {
        Some(c) => c,
        None => {
            info!(0, "Could not open config file: {}", cli_args.config_file.display());
            std::process::exit(1);
        }
    };

    if !config.errors.is_empty() {
        info!(0, "Found Config {} error(s):", config.errors.len());
        info!(0, "Parsed {} below:", cli_args.config_file.display());
        for e in &config.errors {
            info!(0, "{}", format!("{e}").red());
        }
        std::process::exit(1);
    }

    config.log_test_info();

    let success = match cli_args.mode {
        Mode::Regular => RegularHarness::new().run(&config, &cli_args),
        Mode::Tournament => TournamentHarness::new().run(&config, &cli_args),
        Mode::Memcheck => MemoryCheckHarness::new().run(&config, &cli_args),
        Mode::Perf => PerformanceTestingHarness::new().run(&config, &cli_args),
    };

    std::process::exit(if success { 0 } else { 1 });
}
