use std::fmt;
use std::path::PathBuf;

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
    pub config_file: PathBuf,

    /// Path to write failure log (tournament mode)
    #[arg(long = "fail-log")]
    pub failure_log: Option<PathBuf>,

    /// Timeout in seconds for each step
    #[arg(long, default_value_t = 2.0)]
    pub timeout: f64,

    /// Verify CCID in packages
    #[arg(long)]
    pub verify: bool,

    /// Debug a specific package path
    #[arg(long = "debug-package")]
    pub debug_package: Option<String>,

    /// Filter packages by glob pattern (case insensitive)
    #[arg(short = 'p', long = "package")]
    pub package_filter: Option<String>,

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
    #[arg(short = 'o', long = "output")]
    pub output: Option<PathBuf>,

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
    /// Start an HTTP server exposing the test runner API
    Serve {
        /// Path to the JSON configuration file
        config_file: PathBuf,
        /// Address to bind the server to
        #[arg(long, default_value = "127.0.0.1:3000")]
        bind: String,
        /// Timeout in seconds for each step
        #[arg(long, default_value_t = 2.0)]
        timeout: f64,
        /// Maximum number of concurrent test executions
        #[arg(long, default_value_t = 4)]
        max_concurrent: usize,
    },
}

/// Result of parsing CLI arguments — either a runner mode, a script invocation, or a server.
pub enum CliAction {
    Run(RunnerArgs),
    Script(Vec<String>),
    Serve {
        config_file: PathBuf,
        bind: String,
        timeout: f64,
        max_concurrent: usize,
    },
}

/// Parse CLI arguments into a CliAction.
///
/// Supports: `dragon-runner <mode> config.json [flags...]`
///           `dragon-runner script <name> [args...]`
/// If no recognized subcommand is given, defaults to "regular".
pub fn parse_cli_args() -> CliAction {
    let raw_args: Vec<String> = std::env::args().collect();

    // Try parsing as-is first. If that fails, assume the user omitted the
    // subcommand and default to "regular".
    let cli = Cli::try_parse_from(&raw_args).unwrap_or_else(|_| {
        let mut patched = vec![raw_args[0].clone(), "regular".to_string()];
        patched.extend_from_slice(&raw_args[1..]);
        Cli::parse_from(patched)
    });

    match cli.command {
        Commands::Script { args } => CliAction::Script(args),
        Commands::Serve { config_file, bind, timeout, max_concurrent } => {
            CliAction::Serve { config_file, bind, timeout, max_concurrent }
        }
        commands => {
            let (mode, mut args) = match commands {
                Commands::Regular { flags } => (Mode::Regular, flags),
                Commands::Tournament { flags } => (Mode::Tournament, flags),
                Commands::Perf { flags } => (Mode::Perf, flags),
                Commands::Memcheck { flags } => (Mode::Memcheck, flags),
                Commands::Script { .. } | Commands::Serve { .. } => unreachable!(),
            };
            args.mode = mode;

            crate::log::set_debug_level(args.verbosity as u32);

            CliAction::Run(args)
        }
    }
}
