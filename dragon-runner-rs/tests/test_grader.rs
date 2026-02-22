use std::path::Path;

use dragon_runner_rs::cli::{Mode, RunnerArgs};
use dragon_runner_rs::config::load_config;
use dragon_runner_rs::harness::{TestHarness, TournamentHarness};

fn configs_dir() -> std::path::PathBuf {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap().join("tests").join("configs")
}

fn config_path(name: &str) -> String {
    configs_dir().join(name).to_string_lossy().into_owned()
}

#[test]
fn test_grader_config() {
    let path = config_path("ConfigGrade.json");
    let config = load_config(&path, None).expect("config should load");

    let failure_log = "Failures_rs.txt";
    // Clean up from previous runs
    let _ = std::fs::remove_file(failure_log);

    let args = RunnerArgs {
        mode: Mode::Tournament,
        failure_log: failure_log.to_string(),
        timeout: 2.0,
        ..Default::default()
    };

    let mut harness = TournamentHarness::new(config, args);
    harness.run();

    assert!(
        Path::new(failure_log).exists(),
        "failure log should have been created"
    );

    // Clean up
    let _ = std::fs::remove_file(failure_log);
}
