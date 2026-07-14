use std::path::PathBuf;
use std::process::Command;

/// Directory containing grading scripts.
/// Uses CARGO_MANIFEST_DIR baked in at compile time, so it works for both
/// `cargo run` and `cargo install --path .` (as long as the source tree remains).
/// Override with DRAGON_RUNNER_SCRIPTS env var if needed.
fn scripts_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("DRAGON_RUNNER_SCRIPTS") {
        return PathBuf::from(dir);
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scripts")
}

/// (CLI name, Python module filename) for each available script.
const SCRIPTS: &[(&str, &str)] = &[
    ("add_empty", "add_empty.py"),
    ("build", "build.py"),
    ("clean-build", "clean_build.py"),
    ("checkout", "checkout.py"),
    ("gather", "gather.py"),
    ("gen-config", "gen_config.py"),
];

pub fn run_script(args: Vec<String>) -> i32 {
    if args.is_empty() {
        eprintln!("Available scripts:");
        for (name, _) in SCRIPTS {
            eprintln!("  {}", name);
        }
        return 1;
    }

    let script_name = &args[0];
    let module = match SCRIPTS.iter().find(|(name, _)| name == script_name) {
        Some((_, m)) => m,
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
