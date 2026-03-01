use std::sync::atomic::{AtomicU32, Ordering};

static DEBUG_LEVEL: AtomicU32 = AtomicU32::new(0);

/// Set the global debug/verbosity level.
pub fn set_debug_level(level: u32) {
    DEBUG_LEVEL.store(level, Ordering::Relaxed);
}

/// Log a message at a given verbosity level with indentation.
pub fn log(level: u32, indent: usize, msg: &str) {
    if DEBUG_LEVEL.load(Ordering::Relaxed) >= level {
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
