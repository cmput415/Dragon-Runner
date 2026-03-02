use std::sync::atomic::{AtomicU32, Ordering};

static DEBUG_LEVEL: AtomicU32 = AtomicU32::new(0);

/// Set the global debug/verbosity level.
pub fn set_debug_level(level: u32) {
    DEBUG_LEVEL.store(level, Ordering::Relaxed);
}

/// Log a message at a given verbosity level with indentation.
/// Use the `info!`, `debug!`, `trace!`, or `trace2!` macros instead of calling this directly.
#[doc(hidden)]
pub fn log(level: u32, indent: usize, msg: &str) {
    if DEBUG_LEVEL.load(Ordering::Relaxed) >= level {
        println!("{:indent$}{msg}", "", indent = indent);
    }
}

/// Always printed (level 0).
#[macro_export]
macro_rules! info {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(0, $indent, &format!($($arg)*))
    };
}

/// Printed with -v (level 1).
#[macro_export]
macro_rules! debug {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(1, $indent, &format!($($arg)*))
    };
}

/// Printed with -vv (level 2).
#[macro_export]
macro_rules! trace {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(2, $indent, &format!($($arg)*))
    };
}

/// Printed with -vvv (level 3).
#[macro_export]
macro_rules! trace2 {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(3, $indent, &format!($($arg)*))
    };
}
