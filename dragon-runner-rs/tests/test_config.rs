use std::path::{Path, PathBuf};

use dragon_runner_rs::config::load_config;

fn configs_dir() -> PathBuf {
    // tests/configs/ lives at the repo root level, two levels up from dragon-runner-rs/tests/
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap().join("tests").join("configs")
}

fn config_path(name: &str) -> String {
    configs_dir().join(name).to_string_lossy().into_owned()
}

#[test]
fn test_valid_config() {
    let path = config_path("gccPassConfig.json");
    let config = load_config(&path, None).expect("config should load");

    assert!(
        Path::new(&config.test_dir).exists(),
        "test_dir should exist: {}",
        config.test_dir
    );
    assert!(!config.packages.is_empty(), "should have packages");

    for pkg in &config.packages {
        assert!(!pkg.subpackages.is_empty(), "package {} should have subpackages", pkg.name);
        for spkg in &pkg.subpackages {
            assert!(!spkg.tests.is_empty(), "subpackage {} should have tests", spkg.name);
        }
    }

    assert!(
        !config.error_collection.has_errors(),
        "should have no errors, got: {}",
        config.error_collection
    );
}

#[test]
fn test_package_filter() {
    let path = config_path("gccPassConfig.json");
    let config = load_config(&path, None).expect("config should load");

    // Collect all subpackage paths
    let all_subpackages: Vec<&str> = config
        .packages
        .iter()
        .flat_map(|pkg| pkg.subpackages.iter())
        .map(|spkg| spkg.path.as_str())
        .collect();

    assert!(!all_subpackages.is_empty(), "should have subpackages");

    // Test filter pattern "*ErrorPass*"
    let filter_pattern = "*ErrorPass*";
    let filtered: Vec<&&str> = all_subpackages
        .iter()
        .filter(|path| {
            glob::Pattern::new(&filter_pattern.to_lowercase())
                .map(|pat| pat.matches(&path.to_lowercase()))
                .unwrap_or(false)
        })
        .collect();

    assert!(!filtered.is_empty(), "filter should match some subpackages");

    for path in &filtered {
        assert!(
            path.to_lowercase().contains("errorpass"),
            "filtered path should contain 'errorpass': {}",
            path
        );
    }
}

#[test]
fn test_invalid_dir_config() {
    let path = config_path("invalidDirConfig.json");
    let config = load_config(&path, None).expect("config should load");

    assert!(
        config.error_collection.has_errors(),
        "should have errors for invalid dir"
    );
    assert!(
        !Path::new(&config.test_dir).exists(),
        "test_dir should not exist"
    );
}

#[test]
fn test_invalid_exe_config() {
    let path = config_path("invalidExeConfig.json");
    let config = load_config(&path, None).expect("config should load");

    assert!(
        config.error_collection.has_errors(),
        "should have errors for invalid exe"
    );
    assert_eq!(config.executables.len(), 1);
    assert!(
        !Path::new(&config.executables[0].exe_path).exists(),
        "exe_path should not exist"
    );
}
