use std::path::Path;
use std::process;

use dragon_runner_rs::config::{load_config, Config};
use dragon_runner_rs::runner::ToolChainRunner;

fn configs_dir() -> std::path::PathBuf {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap().join("tests").join("configs")
}

fn config_path(name: &str) -> String {
    configs_dir().join(name).to_string_lossy().into_owned()
}

fn tests_dir() -> std::path::PathBuf {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap().join("tests")
}

fn run_tests_for_config(config: &Config, expected_result: bool) {
    for exe in &config.executables {
        exe.source_env();
        for tc in &config.toolchains {
            let runner = ToolChainRunner::new(tc.clone(), 3.0);
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
fn test_gcc_toolchain_success() {
    let test_dir = tests_dir();
    let compile_script = test_dir.join("scripts/test-scripts/compile_lib.py");
    let lib_src_dir = test_dir.join("lib/src");
    let lib_out_dir = test_dir.join("lib");

    assert!(compile_script.exists(), "missing compile_lib.py");

    let expected_lib = test_dir.join("lib/libfib.so");
    if !expected_lib.exists() {
        let status = process::Command::new("python3")
            .args([
                compile_script.to_str().unwrap(),
                lib_src_dir.to_str().unwrap(),
                lib_out_dir.to_str().unwrap(),
            ])
            .status()
            .expect("failed to run compile_lib.py");
        assert!(status.success(), "shared object compilation failed");
        assert!(expected_lib.exists(), "failed to create shared object");
    }

    let path = config_path("runtimeConfigLinux.json");
    let config = load_config(&path, None).expect("config should load");
    assert!(
        !config.error_collection.has_errors(),
        "config errors: {}",
        config.error_collection
    );

    run_tests_for_config(&config, true);
}
