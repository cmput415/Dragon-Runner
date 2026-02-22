use std::env;
use std::sync::OnceLock;

static LOGGER: OnceLock<Logger> = OnceLock::new();

struct Logger {
    debug_level: u32,
}

impl Logger {
    fn new() -> Self {
        let debug_level = env::var("DRAGON_RUNNER_DEBUG")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0);
        Self { debug_level }
    }
}

fn get_logger() -> &'static Logger {
    LOGGER.get_or_init(Logger::new)
}

/// Log a message at a given verbosity level with indentation.
pub fn log(level: u32, indent: usize, msg: &str) {
    let logger = get_logger();
    if logger.debug_level >= level {
        let prefix = " ".repeat(indent);
        println!("{prefix}{msg}");
    }
}

/// Log multiline content with indentation.
pub fn log_multiline(content: &str, level: u32, indent: usize) {
    for line in content.lines() {
        log(level, indent, line.trim_end());
    }
}

/// Log a delimiter line.
pub fn log_delimiter(title: &str, level: u32, indent: usize) {
    let delimiter = "-".repeat(20);
    log(level, indent, &format!("{delimiter} {title} {delimiter}"));
}
