use std::path::Path;

use dragon_runner_rs::config::{load_config, Config};
use dragon_runner_rs::runner::ToolChainRunner;

fn configs_dir() -> std::path::PathBuf {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap().join("tests").join("configs")
}

fn config_path(name: &str) -> String {
    configs_dir().join(name).to_string_lossy().into_owned()
}

fn create_config(name: &str) -> Config {
    let path = config_path(name);
    load_config(&path, None).expect("config should load")
}

/// Run all tests for a config and assert they match expected_result.
fn run_tests_for_config(config: &Config, expected_result: bool) {
    for exe in &config.executables {
        exe.source_env();
        for tc in &config.toolchains {
            let runner = ToolChainRunner::new(tc.clone(), 10.0);
            for pkg in &config.packages {
                for spkg in &pkg.subpackages {
                    for test in &spkg.tests {
                        let result = runner.run(test, exe);
                        assert_eq!(
                            result.did_pass, expected_result,
                            "Test {} expected {} but got {}",
                            test.file,
                            if expected_result { "PASS" } else { "FAIL" },
                            if result.did_pass { "PASS" } else { "FAIL" },
                        );
                    }
                }
            }
        }
    }
}

#[test]
fn test_gcc_pass() {
    let config = create_config("gccPassConfig.json");
    assert!(
        !config.error_collection.has_errors(),
        "config errors: {}",
        config.error_collection
    );
    run_tests_for_config(&config, true);
}

#[test]
fn test_gcc_fail() {
    let config = create_config("gccFailConfig.json");
    assert!(
        !config.error_collection.has_errors(),
        "config errors: {}",
        config.error_collection
    );
    run_tests_for_config(&config, false);
}
