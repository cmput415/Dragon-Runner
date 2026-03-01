use std::process::Command;

use colored::Colorize;

use dragon_runner_rs::cli::{parse_cli_args, CliAction, Mode};
use dragon_runner_rs::config::load_config;
use dragon_runner_rs::harness::*;
use dragon_runner_rs::log::log;

/// Directory containing grading scripts.
/// Uses CARGO_MANIFEST_DIR baked in at compile time, so it works for both
/// `cargo run` and `cargo install --path .` (as long as the source tree remains).
/// Override with DRAGON_RUNNER_SCRIPTS env var if needed.
fn scripts_dir() -> std::path::PathBuf {
    if let Ok(dir) = std::env::var("DRAGON_RUNNER_SCRIPTS") {
        return std::path::PathBuf::from(dir);
    }
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scripts")
}

/// Map script CLI names to their Python module filenames.
fn script_module(name: &str) -> Option<&'static str> {
    match name {
        "add_empty" => Some("add_empty.py"),
        "build" => Some("build.py"),
        "clean-build" => Some("clean_build.py"),
        "checkout" => Some("checkout.py"),
        "gather" => Some("gather.py"),
        "gen-config" => Some("gen_config.py"),
        "grade" => Some("grade.py"),
        "grade-perf" => Some("grade_perf.py"),
        _ => None,
    }
}

fn run_script(args: Vec<String>) -> i32 {
    if args.is_empty() {
        let names = [
            "add_empty", "build", "clean-build", "checkout",
            "gather", "gen-config", "grade", "grade-perf",
        ];
        eprintln!("Available scripts:");
        for name in &names {
            eprintln!("  {}", name);
        }
        return 1;
    }

    let script_name = &args[0];
    let module = match script_module(script_name) {
        Some(m) => m,
        None => {
            eprintln!("Unknown script: {}", script_name);
            return 1;
        }
    };

    let script_path = scripts_dir().join(module);
    if !script_path.exists() {
        eprintln!("Script file not found: {}", script_path.display());
        return 1;
    }

    let status = Command::new("python3")
        .arg(&script_path)
        .args(&args[1..])
        .status();

    match status {
        Ok(s) => s.code().unwrap_or(1),
        Err(e) => {
            eprintln!("Failed to run script: {}", e);
            1
        }
    }
}

fn main() {
    let action = parse_cli_args();

    let cli_args = match action {
        CliAction::Script(args) => {
            std::process::exit(run_script(args));
        }
        CliAction::Run(args) => args,
    };

    log(1, 0, &format!("{:?}", cli_args));

    let config = match load_config(&cli_args.config_file, Some(&cli_args)) {
        Some(c) => c,
        None => {
            log(0, 0, &format!("Could not open config file: {}", cli_args.config_file));
            std::process::exit(1);
        }
    };

    if !config.errors.is_empty() {
        log(0, 0, &format!("Found Config {} error(s):", config.errors.len()));
        log(0, 0, &format!("Parsed {} below:", cli_args.config_file));
        for e in &config.errors {
            log(0, 0, &format!("{e}").red().to_string());
        }
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
