use crate::cli::RunnerArgs;
use crate::error;
use colored::Colorize;
use serde::Deserialize;
use std::fs;
use std::io::{self, Write};
use std::path::Path;

/// Weights and point values used by `compute_scores`.
/// Defaults match the original `scripts/grade.py`; override with `--grade-config`.
#[derive(Debug, Clone, Copy, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GradingConfig {
    #[serde(default = "default_defensive_pts")]
    pub defensive_pts: f64,
    #[serde(default = "default_offensive_pts")]
    pub offensive_pts: f64,
    #[serde(default = "default_coherence_pts")]
    pub coherence_pts: f64,
    #[serde(default = "default_competitive_weight")]
    pub competitive_weight: f64,
    #[serde(default = "default_ta_weight")]
    pub ta_weight: f64,
}

#[rustfmt::skip] fn default_defensive_pts() -> f64 { 2.0 }
#[rustfmt::skip] fn default_offensive_pts() -> f64 { 1.0 }
#[rustfmt::skip] fn default_coherence_pts() -> f64 { 10.0 }
#[rustfmt::skip] fn default_competitive_weight() -> f64 { 0.2 }
#[rustfmt::skip] fn default_ta_weight() -> f64 { 0.5 }

impl Default for GradingConfig {
    fn default() -> Self {
        Self {
            defensive_pts: default_defensive_pts(),
            offensive_pts: default_offensive_pts(),
            coherence_pts: default_coherence_pts(),
            competitive_weight: default_competitive_weight(),
            ta_weight: default_ta_weight(),
        }
    }
}

/// Load the file passed to `--grade-config`, or return defaults. Exits on error.
pub fn resolve_grading_config(cli_args: &RunnerArgs) -> GradingConfig {
    match cli_args.grade_config.as_deref() {
        None => GradingConfig::default(),
        Some(path) => match load_grading_config(path) {
            Ok(c) => c,
            Err(e) => {
                error!(0, "{}", format!("grade config error: {e}").red());
                std::process::exit(1);
            }
        },
    }
}

pub fn load_grading_config(path: &Path) -> Result<GradingConfig, String> {
    let text =
        fs::read_to_string(path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let cfg: GradingConfig =
        serde_json::from_str(&text).map_err(|e| format!("cannot parse {}: {e}", path.display()))?;
    validate_grading_config(&cfg)
        .map_err(|e| format!("invalid grading config {}: {e}", path.display()))?;
    Ok(cfg)
}

fn validate_grading_config(cfg: &GradingConfig) -> Result<(), String> {
    let fields = [
        ("defensivePts", cfg.defensive_pts),
        ("offensivePts", cfg.offensive_pts),
        ("coherencePts", cfg.coherence_pts),
        ("competitiveWeight", cfg.competitive_weight),
        ("taWeight", cfg.ta_weight),
    ];
    for (name, v) in fields {
        if !v.is_finite() || v < 0.0 {
            return Err(format!(
                "{name} must be a finite non-negative number, got {v}"
            ));
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// TournamentTable
// ---------------------------------------------------------------------------

/// One toolchain's results. `cells[i][j]` is (pass, total) for defender `i`
/// against attacker `j`. Defenders and attackers are the same teams in the
/// same order, so the table is square.
#[derive(Debug, Clone)]
pub struct TournamentTable {
    pub toolchain: String,
    pub defenders: Vec<String>,
    pub attackers: Vec<String>,
    pub cells: Vec<Vec<(u32, u32)>>,
}

impl TournamentTable {
    fn pass_fraction(&self, i: usize, j: usize) -> f64 {
        let (pass, total) = self.cells[i][j];
        if total == 0 {
            0.0
        } else {
            pass as f64 / total as f64
        }
    }
}

// ---------------------------------------------------------------------------
// Scores
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Scores {
    pub team_ids: Vec<String>,
    pub defensive: Vec<f64>,
    pub offensive: Vec<f64>,
    pub coherence: Vec<f64>,
    pub ta: Vec<f64>,
    pub competitive_total: Vec<f64>,
    pub normalized: Vec<f64>,
}

/// Average the pass rates across several toolchain tables. All tables must
/// share the same defenders and attackers in the same order. Cells are stored
/// as `(rate * 1000, 1000)` so the result stays integer.
pub fn average_tables(tables: &[TournamentTable]) -> Result<TournamentTable, String> {
    let first = tables
        .first()
        .ok_or("average_tables: need at least one table")?;
    let n = first.defenders.len();
    let m = first.attackers.len();
    for t in tables {
        if t.defenders != first.defenders || t.attackers != first.attackers {
            return Err("average_tables: shape mismatch across tables".into());
        }
    }

    const DENOM: u32 = 1000;
    let mut cells = vec![vec![(0u32, DENOM); m]; n];
    for i in 0..n {
        for j in 0..m {
            let avg: f64 =
                tables.iter().map(|t| t.pass_fraction(i, j)).sum::<f64>() / tables.len() as f64;
            cells[i][j] = ((avg * DENOM as f64).round() as u32, DENOM);
        }
    }

    Ok(TournamentTable {
        toolchain: "average".into(),
        defenders: first.defenders.clone(),
        attackers: first.attackers.clone(),
        cells,
    })
}

/// Score each team from a tournament table.
///
/// A team gets defensive points for surviving other teams' tests and
/// offensive points for breaking other teams' defenses. It gets coherence
/// points if it passes all of its own tests. `ta` is how the reference
/// solution did against that team's tests. Normalized rescales the
/// competitive total so the best team hits `competitive_weight`.
///
/// See the tests at the bottom of this file for a worked example.
pub fn compute_scores(
    table: &TournamentTable,
    cfg: &GradingConfig,
    solution_id: &str,
) -> Result<Scores, String> {
    let n = table.defenders.len();
    if n != table.attackers.len() {
        return Err(format!(
            "compute_scores expects a square table (defenders={}, attackers={})",
            n,
            table.attackers.len()
        ));
    }

    let solution_col = table
        .attackers
        .iter()
        .position(|a| a == solution_id)
        .ok_or_else(|| {
            format!(
                "solution id {solution_id:?} not found among attackers: {:?}",
                table.attackers
            )
        })?;

    let mut defensive = vec![0.0; n];
    let mut offensive = vec![0.0; n];
    let mut coherence = vec![0.0; n];
    let mut ta = vec![0.0; n];

    for j in 0..n {
        let (self_pass, self_total) = table.cells[j][j];
        coherence[j] = if self_total > 0 && self_pass == self_total {
            cfg.coherence_pts
        } else {
            0.0
        };

        ta[j] = table.pass_fraction(j, solution_col);

        for i in 0..n {
            if i != j {
                defensive[j] += cfg.defensive_pts * table.pass_fraction(j, i);
            }
        }
        for k in 0..n {
            if k != j {
                offensive[j] += cfg.offensive_pts * (1.0 - table.pass_fraction(k, j));
            }
        }
    }

    let competitive_total: Vec<f64> = (0..n)
        .map(|j| defensive[j] + offensive[j] + coherence[j])
        .collect();
    let max = competitive_total.iter().cloned().fold(0.0_f64, f64::max);
    let normalized: Vec<f64> = competitive_total
        .iter()
        .map(|&s| {
            if max > 0.0 {
                cfg.competitive_weight * s / max
            } else {
                0.0
            }
        })
        .collect();

    Ok(Scores {
        team_ids: table.defenders.clone(),
        defensive,
        offensive,
        coherence,
        ta,
        competitive_total,
        normalized,
    })
}

// ---------------------------------------------------------------------------
// PerfTable / PerfScores
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct PerfTable {
    pub compilers: Vec<String>,
    pub tests: Vec<String>,
    /// Row is a test, column is a compiler. Timeouts get the timeout value;
    /// missing runs get infinity.
    pub times_seconds: Vec<Vec<f64>>,
}

#[derive(Debug, Clone)]
pub struct PerfScores {
    pub compilers: Vec<String>,
    /// Per-compiler score in [0, 1]. The fastest compiler on every test
    /// scores 1.0; everyone else is a fraction of that.
    pub scores: Vec<f64>,
}

pub fn compute_perf_scores(table: &PerfTable) -> PerfScores {
    let num_compilers = table.compilers.len();
    let mut sums = vec![0.0; num_compilers];
    let mut counts = vec![0usize; num_compilers];

    for row in &table.times_seconds {
        let fastest = row.iter().cloned().fold(f64::INFINITY, f64::min);
        if !fastest.is_finite() || fastest <= 0.0 {
            continue;
        }
        // Extra cells in a malformed row would panic without this take().
        for (c, &t) in row.iter().take(num_compilers).enumerate() {
            if t.is_finite() && t > 0.0 {
                sums[c] += fastest / t;
                counts[c] += 1;
            }
        }
    }

    let scores: Vec<f64> = sums
        .iter()
        .zip(counts.iter())
        .map(|(&s, &c)| if c > 0 { s / c as f64 } else { 0.0 })
        .collect();

    PerfScores {
        compilers: table.compilers.clone(),
        scores,
    }
}

// ---------------------------------------------------------------------------
// I/O helpers 
// ---------------------------------------------------------------------------

fn fmt_cell(cell: (u32, u32)) -> String {
    let (pass, total) = cell;
    format!("{pass}/{total}")
}

pub fn write_tournament_csv(table: &TournamentTable, path: &Path) -> io::Result<()> {
    let mut f = fs::File::create(path)?;
    let header: Vec<&str> = std::iter::once(table.toolchain.as_str())
        .chain(table.attackers.iter().map(String::as_str))
        .collect();
    writeln!(f, "{}", header.join(","))?;
    for (i, defender) in table.defenders.iter().enumerate() {
        let mut row: Vec<String> = vec![defender.clone()];
        for j in 0..table.attackers.len() {
            row.push(fmt_cell(table.cells[i][j]));
        }
        writeln!(f, "{}", row.join(","))?;
    }
    Ok(())
}

pub fn write_summary_csv(
    table: &TournamentTable,
    scores: &Scores,
    cfg: &GradingConfig,
    path: &Path,
) -> io::Result<()> {
    let mut f = fs::File::create(path)?;

    let header: Vec<&str> = std::iter::once("toolchain summary")
        .chain(table.attackers.iter().map(String::as_str))
        .collect();
    writeln!(f, "{}", header.join(","))?;

    for (i, defender) in table.defenders.iter().enumerate() {
        let mut row: Vec<String> = vec![defender.clone()];
        for j in 0..table.attackers.len() {
            let frac = table.pass_fraction(i, j);
            row.push(format!("{:.3}", frac));
        }
        writeln!(f, "{}", row.join(","))?;
    }

    let row = |label: &str, values: &[f64], precision: usize| -> String {
        let mut cells: Vec<String> = vec![label.into()];
        for v in values {
            cells.push(format!("{v:.*}", precision));
        }
        cells.join(",")
    };

    writeln!(f, "{}", row("Defensive Points", &scores.defensive, 2))?;
    writeln!(f, "{}", row("Offensive Points", &scores.offensive, 2))?;
    writeln!(f, "{}", row("Coherence Points", &scores.coherence, 0))?;
    writeln!(
        f,
        "{}",
        row("Competitive Points", &scores.competitive_total, 2)
    )?;

    let ta_weighted: Vec<f64> = scores.ta.iter().map(|s| s * cfg.ta_weight).collect();
    writeln!(
        f,
        "{}",
        row(
            &format!("TA Testing Score ({:.0}% Weight)", cfg.ta_weight * 100.0),
            &ta_weighted,
            3
        )
    )?;
    writeln!(
        f,
        "{}",
        row(
            &format!(
                "Normalized Points ({:.0}% Weight)",
                cfg.competitive_weight * 100.0
            ),
            &scores.normalized,
            3
        )
    )?;

    Ok(())
}

pub fn write_perf_csv(table: &PerfTable, path: &Path) -> io::Result<()> {
    let mut f = fs::File::create(path)?;
    let mut header: Vec<&str> = vec!["Test"];
    header.extend(table.compilers.iter().map(String::as_str));
    writeln!(f, "{}", header.join(","))?;
    for (i, test) in table.tests.iter().enumerate() {
        let mut row: Vec<String> = vec![test.clone()];
        for &t in &table.times_seconds[i] {
            row.push(format!("{t:.4}"));
        }
        writeln!(f, "{}", row.join(","))?;
    }
    Ok(())
}

pub fn write_perf_summary_csv(scores: &PerfScores, path: &Path) -> io::Result<()> {
    let mut f = fs::File::create(path)?;
    writeln!(f, "{}", scores.compilers.join(","))?;
    let cells: Vec<String> = scores.scores.iter().map(|s| format!("{s:.4}")).collect();
    writeln!(f, "{}", cells.join(","))?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn table(defenders: &[&str], cells: Vec<Vec<(u32, u32)>>) -> TournamentTable {
        TournamentTable {
            toolchain: "t".into(),
            defenders: defenders.iter().map(|s| (*s).into()).collect(),
            attackers: defenders.iter().map(|s| (*s).into()).collect(),
            cells,
        }
    }

    fn approx_eq(a: f64, b: f64) {
        assert!((a - b).abs() < 1e-9, "expected {b}, got {a}");
    }

    #[test]
    fn grading_config_defaults_match_legacy_constants() {
        let cfg = GradingConfig::default();
        assert_eq!(cfg.defensive_pts, 2.0);
        assert_eq!(cfg.offensive_pts, 1.0);
        assert_eq!(cfg.coherence_pts, 10.0);
        assert_eq!(cfg.competitive_weight, 0.2);
        assert_eq!(cfg.ta_weight, 0.5);
    }

    #[test]
    fn grading_config_partial_json_uses_defaults_for_missing() {
        let cfg: GradingConfig = serde_json::from_str(r#"{"defensivePts": 5.0}"#).unwrap();
        assert_eq!(cfg.defensive_pts, 5.0);
        assert_eq!(cfg.offensive_pts, 1.0);
        assert_eq!(cfg.coherence_pts, 10.0);
    }

    #[test]
    fn compute_scores_identity_matrix() {
        // Every team passes only its own tests.
        let cfg = GradingConfig::default();
        let t = table(
            &["A", "B", "C"],
            vec![
                vec![(2, 2), (0, 2), (0, 2)],
                vec![(0, 2), (2, 2), (0, 2)],
                vec![(0, 2), (0, 2), (2, 2)],
            ],
        );
        let s = compute_scores(&t, &cfg, "A").unwrap();

        // Each team passes its own tests.
        for c in &s.coherence {
            approx_eq(*c, 10.0);
        }
        // No team passes another team's tests.
        for d in &s.defensive {
            approx_eq(*d, 0.0);
        }
        // Each other team fully fails our tests.
        for o in &s.offensive {
            approx_eq(*o, 2.0);
        }
        // ta = fraction A (solution) passed against each defender's tests.
        // For j=0 (A itself), self-cell is 2/2 = 1.0.
        // For j=1 (B), cell[1][0] = 0/2 = 0.0.
        approx_eq(s.ta[0], 1.0);
        approx_eq(s.ta[1], 0.0);
        approx_eq(s.ta[2], 0.0);
    }

    #[test]
    fn compute_scores_hand_computed_3x3() {
        // Deliberate spread:
        //   A defends perfectly and attacks weakly.
        //   B fails on its own tests (breaks coherence).
        //   C is average.
        //
        //          attacker: A       B       C
        //   defender A:      4/4     4/4     4/4     <- A passes everything
        //   defender B:      2/4     2/4     0/4     <- B is flaky
        //   defender C:      3/4     3/4     3/4     <- C consistent
        //
        // pass_fraction table:
        //   A: 1.0, 1.0, 1.0
        //   B: 0.5, 0.5, 0.0
        //   C: 0.75, 0.75, 0.75
        //
        // defensive_pts = 2, offensive_pts = 1, coherence_pts = 10.
        //
        // defensive[A] = 2 * (1.0 + 1.0) = 4.0
        // defensive[B] = 2 * (0.5 + 0.0) = 1.0
        // defensive[C] = 2 * (0.75 + 0.75) = 3.0
        //
        // offensive[A] = 1 * ((1-0.5) + (1-0.75)) = 0.75
        // offensive[B] = 1 * ((1-1.0) + (1-0.75)) = 0.25
        // offensive[C] = 1 * ((1-1.0) + (1-0.0)) = 1.0
        //
        // coherence[A] = 10 (self-cell 4/4), coherence[B] = 0 (2/4), coherence[C] = 0 (3/4)
        //
        // ta[j] uses solution column A (index 0):
        //   ta[A] = pass_fraction(A, A) = 1.0
        //   ta[B] = pass_fraction(B, A) = 0.5
        //   ta[C] = pass_fraction(C, A) = 0.75
        let cfg = GradingConfig::default();
        let t = table(
            &["A", "B", "C"],
            vec![
                vec![(4, 4), (4, 4), (4, 4)],
                vec![(2, 4), (2, 4), (0, 4)],
                vec![(3, 4), (3, 4), (3, 4)],
            ],
        );
        let s = compute_scores(&t, &cfg, "A").unwrap();

        approx_eq(s.defensive[0], 4.0);
        approx_eq(s.defensive[1], 1.0);
        approx_eq(s.defensive[2], 3.0);

        approx_eq(s.offensive[0], 0.75);
        approx_eq(s.offensive[1], 0.25);
        approx_eq(s.offensive[2], 1.0);

        approx_eq(s.coherence[0], 10.0);
        approx_eq(s.coherence[1], 0.0);
        approx_eq(s.coherence[2], 0.0);

        approx_eq(s.ta[0], 1.0);
        approx_eq(s.ta[1], 0.5);
        approx_eq(s.ta[2], 0.75);

        // Competitive totals: A=14.75, B=1.25, C=4.0. Max=14.75.
        approx_eq(s.competitive_total[0], 14.75);
        approx_eq(s.competitive_total[1], 1.25);
        approx_eq(s.competitive_total[2], 4.0);

        // Normalized = 0.2 * total / max.
        approx_eq(s.normalized[0], 0.2 * 14.75 / 14.75);
        approx_eq(s.normalized[1], 0.2 * 1.25 / 14.75);
        approx_eq(s.normalized[2], 0.2 * 4.0 / 14.75);
    }

    #[test]
    fn average_tables_means_pass_fractions() {
        let a = table(
            &["X", "Y"],
            vec![vec![(4, 4), (0, 4)], vec![(0, 4), (4, 4)]],
        );
        let b = table(
            &["X", "Y"],
            vec![vec![(2, 4), (2, 4)], vec![(2, 4), (2, 4)]],
        );
        let avg = average_tables(&[a, b]).unwrap();
        // (1.0 + 0.5) / 2 = 0.75
        assert_eq!(avg.cells[0][0], (750, 1000));
        // (0.0 + 0.5) / 2 = 0.25
        assert_eq!(avg.cells[0][1], (250, 1000));
        assert_eq!(avg.cells[1][0], (250, 1000));
        assert_eq!(avg.cells[1][1], (750, 1000));
    }

    #[test]
    fn perf_scores_fastest_gets_one() {
        let t = PerfTable {
            compilers: vec!["fast".into(), "slow".into()],
            tests: vec!["t1".into(), "t2".into()],
            times_seconds: vec![vec![1.0, 2.0], vec![0.5, 1.0]],
        };
        let s = compute_perf_scores(&t);
        // Column 0 is fastest in both rows.
        approx_eq(s.scores[0], 1.0);
        // slow: mean(0.5, 0.5) = 0.5
        approx_eq(s.scores[1], 0.5);
    }
}
