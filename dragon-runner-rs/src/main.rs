use colored::Colorize;

use dragon_runner_rs::cli::{parse_cli_args, Mode};
use dragon_runner_rs::config::load_config;
use dragon_runner_rs::harness::*;
use dragon_runner_rs::log::log;

fn main() {
    let cli_args = parse_cli_args();
    log(1, 0, &format!("{:?}", cli_args));

    let config = match load_config(&cli_args.config_file, Some(&cli_args)) {
        Some(c) => c,
        None => {
            log(0, 0, &format!("Could not open config file: {}", cli_args.config_file));
            std::process::exit(1);
        }
    };

    if config.error_collection.has_errors() {
        log(
            0,
            0,
            &format!(
                "Found Config {} error(s):",
                config.error_collection.len()
            ),
        );
        log(
            0,
            0,
            &format!("Parsed {} below:", cli_args.config_file),
        );
        log(
            0,
            0,
            &format!("{}", config.error_collection).red().to_string(),
        );
        std::process::exit(1);
    }

    if cli_args.verify {
        // CCID verification
        let mut input = String::new();
        println!("Enter your CCID/Github Team Name: ");
        std::io::stdin()
            .read_line(&mut input)
            .expect("Failed to read input");
        let ccid = input.trim();

        let found = config.packages.iter().any(|pkg| {
            log(0, 2, &format!("Searching..  {}", pkg.name));
            pkg.name == ccid
        });

        if !found {
            println!("Could not find package named after CCID: {}", ccid);
            std::process::exit(1);
        }
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
