use std::fmt;

use clap::{Args, Parser, Subcommand};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Mode {
    #[default]
    Regular,
    Tournament,
    Perf,
    Memcheck,
}

impl fmt::Display for Mode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Mode::Regular => write!(f, "regular"),
            Mode::Tournament => write!(f, "tournament"),
            Mode::Perf => write!(f, "perf"),
            Mode::Memcheck => write!(f, "memcheck"),
        }
    }
}

/// Shared flags available in all modes (also used as the runtime args type).
#[derive(Args, Debug, Clone, Default)]
pub struct RunnerArgs {
    /// Set by the subcommand, not by clap.
    #[arg(skip)]
    pub mode: Mode,

    /// Path to the JSON configuration file
    pub config_file: String,

    /// Path to write failure log
    #[arg(long = "fail-log", default_value = "")]
    pub failure_log: String,

    /// Timeout in seconds for each step
    #[arg(long, default_value_t = 2.0)]
    pub timeout: f64,

    /// Verify CCID in packages
    #[arg(long)]
    pub verify: bool,

    /// Debug a specific package path
    #[arg(long = "debug-package", default_value = "")]
    pub debug_package: String,

    /// Filter packages by glob pattern (case insensitive)
    #[arg(short = 'p', long = "package", default_value = "")]
    pub package_filter: String,

    /// Show timing information
    #[arg(short = 't', long = "time")]
    pub time: bool,

    /// Increase verbosity (can be repeated: -v, -vv, -vvv)
    #[arg(short = 'v', long = "verbosity", action = clap::ArgAction::Count)]
    pub verbosity: u8,

    /// Show test case contents on failure
    #[arg(short = 's', long = "show-testcase")]
    pub show_testcase: bool,

    /// Output file path
    #[arg(short = 'o', long = "output", default_value = "")]
    pub output: String,

    /// Stop on first failure
    #[arg(short = 'f', long = "fast-fail")]
    pub fast_fail: bool,
}

/// CMPUT 415 testing utility
#[derive(Parser, Debug)]
#[command(name = "dragon-runner", about = "CMPUT 415 testing utility")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand, Debug)]
pub enum Commands {
    /// Run in regular mode (default)
    Regular {
        #[command(flatten)]
        flags: RunnerArgs,
    },
    /// Run in tournament/grading mode
    Tournament {
        #[command(flatten)]
        flags: RunnerArgs,
    },
    /// Run performance tests
    Perf {
        #[command(flatten)]
        flags: RunnerArgs,
    },
    /// Run with memory checking (valgrind)
    Memcheck {
        #[command(flatten)]
        flags: RunnerArgs,
    },
    /// Run a grading script
    Script {
        /// Script name and arguments
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        args: Vec<String>,
    },
}

/// Result of parsing CLI arguments — either a runner mode or a script invocation.
pub enum CliAction {
    Run(RunnerArgs),
    Script(Vec<String>),
}

/// Parse CLI arguments into a CliAction.
///
/// Supports: `dragon-runner <mode> config.json [flags...]`
///           `dragon-runner script <name> [args...]`
/// If no recognized mode is given, inserts "regular" so clap can parse it.
pub fn parse_cli_args() -> CliAction {
    let raw_args: Vec<String> = std::env::args().collect();

    // If the user omits the mode subcommand, default to "regular".
    // Detect this by checking whether the second arg is a known subcommand.
    let known_modes = ["regular", "tournament", "perf", "memcheck", "script"];
    let args_to_parse = if raw_args.len() >= 2 && !known_modes.contains(&raw_args[1].as_str()) && !raw_args[1].starts_with('-') {
        // Insert "regular" as the subcommand
        let mut patched = vec![raw_args[0].clone(), "regular".to_string()];
        patched.extend_from_slice(&raw_args[1..]);
        patched
    } else {
        raw_args
    };

    let cli = Cli::parse_from(args_to_parse);

    match cli.command {
        Commands::Script { args } => CliAction::Script(args),
        commands => {
            let (mode, mut args) = match commands {
                Commands::Regular { flags } => (Mode::Regular, flags),
                Commands::Tournament { flags } => (Mode::Tournament, flags),
                Commands::Perf { flags } => (Mode::Perf, flags),
                Commands::Memcheck { flags } => (Mode::Memcheck, flags),
                Commands::Script { .. } => unreachable!(),
            };
            args.mode = mode;

            crate::log::set_debug_level(args.verbosity as u32);

            CliAction::Run(args)
        }
    }
}
