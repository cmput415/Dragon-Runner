use std::env;
use std::sync::atomic::{AtomicU32, Ordering};

static DEBUG_LEVEL: AtomicU32 = AtomicU32::new(u32::MAX);

fn debug_level() -> u32 {
    let cached = DEBUG_LEVEL.load(Ordering::Relaxed);
    if cached != u32::MAX {
        return cached;
    }
    let level = env::var("DRAGON_RUNNER_DEBUG")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);
    DEBUG_LEVEL.store(level, Ordering::Relaxed);
    level
}

/// Re-read DRAGON_RUNNER_DEBUG from the environment.
/// Call after setting the env var (e.g. from CLI parsing).
pub fn refresh_debug_level() {
    let level = env::var("DRAGON_RUNNER_DEBUG")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);
    DEBUG_LEVEL.store(level, Ordering::Relaxed);
}

/// Log a message at a given verbosity level with indentation.
pub fn log(level: u32, indent: usize, msg: &str) {
    if debug_level() >= level {
        println!("{:indent$}{msg}", "", indent = indent);
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
    let delim = "-".repeat(20);
    log(level, indent, &format!("{delim} {title} {delim}"));
}
