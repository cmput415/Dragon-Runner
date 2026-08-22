use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("configs")
        .join(name)
}

fn run_dragon_runner(current_dir: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_dragon-runner"))
        .current_dir(current_dir)
        .args(args)
        .output()
        .expect("dragon-runner should start")
}

fn output_context(output: &Output) -> String {
    format!(
        "status: {}\nstdout:\n{}\nstderr:\n{}",
        output.status,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr),
    )
}

fn read(path: &Path) -> String {
    fs::read_to_string(path).unwrap_or_else(|e| panic!("failed to read {}: {e}", path.display()))
}

#[test]
fn tournament_cli_writes_complete_grading_bundle() {
    let out_dir = tempfile::tempdir().expect("temporary output directory");
    let config = fixture("E2ETournament.json");
    let grading_config = fixture("E2EGrading.json");

    let output = run_dragon_runner(
        out_dir.path(),
        &[
            "tournament",
            config.to_str().unwrap(),
            "--solution-exe",
            "team_B",
            "--grade-config",
            grading_config.to_str().unwrap(),
            "--fail-log",
            "failure_log.txt",
            "--timeout",
            "0.1",
        ],
    );
    assert!(output.status.success(), "{}", output_context(&output));

    let expected_toolchain = "\
one_step,TA,team_A,team_B,team_C
TA,4/4,4/4,4/4,4/4
team_A,3/4,3/4,3/4,3/4
team_B,2/4,2/4,2/4,2/4
team_C,1/4,1/4,1/4,1/4
";
    assert_eq!(
        read(&out_dir.path().join("toolchain_one_step.csv")),
        expected_toolchain,
    );

    let expected_summary = "\
toolchain summary,TA,team_A,team_B,team_C
TA,1.000,1.000,1.000,1.000
team_A,0.750,0.750,0.750,0.750
team_B,0.500,0.500,0.500,0.500
team_C,0.250,0.250,0.250,0.250
Defensive Points,9.00,6.75,4.50,2.25
Offensive Points,1.50,1.25,1.00,0.75
Coherence Points,10,0,0,0
Competitive Points,20.50,8.00,5.50,3.00
TA Testing Score (50% Weight),0.500,0.375,0.250,0.125
Normalized Points (20% Weight),0.200,0.078,0.054,0.029
";
    assert_eq!(read(&out_dir.path().join("summary.csv")), expected_summary);

    let pass_log = read(&out_dir.path().join("pass_log.txt"));
    let failure_log = read(&out_dir.path().join("failure_log.txt"));
    assert_eq!(pass_log.lines().count(), 8);
    assert_eq!(failure_log.lines().count(), 8);
    assert!(pass_log.lines().all(|line| line.starts_with("one_step ")));
    assert!(failure_log
        .lines()
        .all(|line| line.starts_with("one_step ")));
    assert_eq!(pass_log.matches("01_basic.c").count(), 4);
    assert_eq!(pass_log.matches("04_gamma.c").count(), 4);
    assert_eq!(failure_log.matches("02_alpha.c").count(), 4);
    assert_eq!(failure_log.matches("03_beta.c").count(), 4);

    for (team, failure_count) in [("team_A", 4), ("team_B", 8), ("team_C", 12)] {
        let feedback = read(&out_dir.path().join(format!("{team}-one_stepfeedback.txt")));
        assert_eq!(
            feedback.matches("Test: ").count(),
            failure_count,
            "unexpected feedback entry count for {team}",
        );
        assert!(feedback.contains("Expected Output:"));
        assert!(feedback.contains("Generated Output:"));
    }
    assert!(!out_dir.path().join("TA-one_stepfeedback.txt").exists());
}

#[test]
fn tournament_cli_rejects_missing_solution_without_artifacts() {
    let out_dir = tempfile::tempdir().expect("temporary output directory");
    let config = fixture("E2ETournament.json");
    let output = run_dragon_runner(out_dir.path(), &["tournament", config.to_str().unwrap()]);

    assert!(!output.status.success(), "{}", output_context(&output));
    assert!(
        String::from_utf8_lossy(&output.stderr)
            .contains("--solution-exe is required in tournament mode"),
        "{}",
        output_context(&output),
    );
    assert_eq!(
        fs::read_dir(out_dir.path()).unwrap().count(),
        0,
        "a rejected grading run should not leave partial artifacts",
    );
}
