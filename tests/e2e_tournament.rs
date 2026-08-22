//! End-to-end tournament grading test.
//!
//! Runs a small tournament using four shell-script "compilers" with distinct
//! failure modes (perfect / exit-fail / timeout / total wreck) against four
//! identical attacker packages of four tests each. Verifies the pass/fail
//! matrix has the expected shape and that `compute_scores` produces the
//! hand-derived numbers below.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use dragon_runner_rs::cli::{Mode, RunnerArgs};
use dragon_runner_rs::config::load_config;
use dragon_runner_rs::grading::{compute_scores, load_grading_config};
use dragon_runner_rs::harness::TournamentHarness;

fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("configs")
        .join(name)
}

fn approx_eq(actual: f64, expected: f64, ctx: &str) {
    assert!(
        (actual - expected).abs() < 1e-6,
        "{ctx}: expected {expected}, got {actual}",
    );
}

#[test]
fn e2e_tournament_scores_show_full_spread() {
    let config = load_config(&fixture("E2ETournament.json"), None)
        .expect("E2ETournament config should load");
    let grading_cfg =
        load_grading_config(&fixture("E2EGrading.json")).expect("E2EGrading config should load");

    let args = RunnerArgs {
        mode: Mode::Tournament,
        solution_exe: Some("TA".into()),
        timeout: 1.0,
        ..Default::default()
    };

    let output = TournamentHarness::new()
        .run(&config, &args)
        .expect("tournament should run");

    assert_eq!(output.tables.len(), 1, "one toolchain expected");
    let table = &output.tables[0];
    assert_eq!(table.toolchain, "one_step");

    // Names are sorted case-insensitively.
    let expected_order: Vec<String> = vec!["TA", "team_A", "team_B", "team_C"]
        .into_iter()
        .map(String::from)
        .collect();
    assert_eq!(table.defenders, expected_order);
    assert_eq!(table.attackers, expected_order);

    // Identical packages give each row the same pass count.
    let expected_cells: Vec<(u32, u32)> = vec![
        (4, 4), // TA: passes everything
        (3, 4), // team_A: fails ALPHA
        (2, 4), // team_B: fails ALPHA + times out on BETA
        (1, 4), // team_C: fails ALPHA, BETA, GAMMA
    ];
    for (i, exp) in expected_cells.iter().enumerate() {
        for j in 0..4 {
            assert_eq!(
                table.cells[i][j], *exp,
                "cell[{i}][{j}] ({} vs {}) mismatch",
                table.defenders[i], table.attackers[j],
            );
        }
    }

    let scores = compute_scores(table, &grading_cfg, "TA").unwrap();
    assert_eq!(scores.team_ids, expected_order);

    // Hand-computed values (see comment block below the test).
    approx_eq(scores.coherence[0], 10.0, "coherence[TA]");
    approx_eq(scores.coherence[1], 0.0, "coherence[team_A]");
    approx_eq(scores.coherence[2], 0.0, "coherence[team_B]");
    approx_eq(scores.coherence[3], 0.0, "coherence[team_C]");

    approx_eq(scores.ta[0], 1.0, "ta[TA]");
    approx_eq(scores.ta[1], 0.75, "ta[team_A]");
    approx_eq(scores.ta[2], 0.5, "ta[team_B]");
    approx_eq(scores.ta[3], 0.25, "ta[team_C]");

    approx_eq(scores.defensive[0], 9.0, "defensive[TA]");
    approx_eq(scores.defensive[1], 6.75, "defensive[team_A]");
    approx_eq(scores.defensive[2], 4.5, "defensive[team_B]");
    approx_eq(scores.defensive[3], 2.25, "defensive[team_C]");

    approx_eq(scores.offensive[0], 1.5, "offensive[TA]");
    approx_eq(scores.offensive[1], 1.25, "offensive[team_A]");
    approx_eq(scores.offensive[2], 1.0, "offensive[team_B]");
    approx_eq(scores.offensive[3], 0.75, "offensive[team_C]");

    approx_eq(scores.competitive_total[0], 20.5, "competitive_total[TA]");
    approx_eq(
        scores.competitive_total[1],
        8.0,
        "competitive_total[team_A]",
    );
    approx_eq(
        scores.competitive_total[2],
        5.5,
        "competitive_total[team_B]",
    );
    approx_eq(
        scores.competitive_total[3],
        3.0,
        "competitive_total[team_C]",
    );

    // Four distinct competitive totals confirm real spread across defenders.
    let unique: HashSet<u64> = scores
        .competitive_total
        .iter()
        .map(|f| f.to_bits())
        .collect();
    assert_eq!(unique.len(), 4, "expected 4 distinct competitive totals");

    // Failure counts are 4 + 8 + 12.
    assert_eq!(output.failures.len(), 24, "unexpected failure count");
    // The solution passes all 16 runs.
    assert_eq!(output.solution_results.len(), 16, "solution results count");
    assert!(
        output.solution_results.iter().all(|r| r.did_pass),
        "TA (solution) should pass every test"
    );
}

// -----------------------------------------------------------------------------
// Hand-derived scores (grade config: defensivePts=3, offensivePts=1,
// coherencePts=10). Pass fractions are constant across attackers because all
// packages share the same four tests.
//
//   TA:      1.0    (4/4)
//   team_A:  0.75   (3/4, fails ALPHA)
//   team_B:  0.5    (2/4, fails ALPHA + times out on BETA)
//   team_C:  0.25   (1/4, fails ALPHA, BETA, GAMMA)
//
// coherence[j] = 10 iff self-cell is a full pass, else 0.
// ta[j]        = pass_fraction against TA's attacker column.
// defensive[j] = 3 * sum over i != j of pass_fraction(j, i).
// offensive[j] = 1 * sum over k != j of (1 - pass_fraction(k, j)).
// -----------------------------------------------------------------------------
