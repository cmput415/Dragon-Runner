use std::fmt::Arguments;
use std::io::{self, Write};
use std::sync::atomic::{AtomicU32, Ordering};

static DEBUG_LEVEL: AtomicU32 = AtomicU32::new(0);

/// Set the global debug/verbosity level.
pub fn set_debug_level(level: u32) {
    DEBUG_LEVEL.store(level, Ordering::Relaxed);
}

#[doc(hidden)]
pub fn log(level: u32, indent: usize, args: Arguments<'_>) {
    if DEBUG_LEVEL.load(Ordering::Relaxed) >= level {
        let stdout = io::stdout();
        let mut stdout = stdout.lock();
        let _ = writeln!(stdout, "{:indent$}{args}", "", indent = indent);
        let _ = stdout.flush();
    }
}

#[doc(hidden)]
pub fn error(indent: usize, args: Arguments<'_>) {
    let stderr = io::stderr();
    let mut stderr = stderr.lock();
    let _ = writeln!(stderr, "{:indent$}{args}", "", indent = indent);
    let _ = stderr.flush();
}

#[doc(hidden)]
pub fn progress(args: Arguments<'_>) {
    let stdout = io::stdout();
    let mut stdout = stdout.lock();
    let _ = write!(stdout, "{args}");
    let _ = stdout.flush();
}

#[macro_export]
macro_rules! info {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(0, $indent, format_args!($($arg)*))
    };
}

#[macro_export]
macro_rules! debug {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(1, $indent, format_args!($($arg)*))
    };
}

#[macro_export]
macro_rules! trace {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(2, $indent, format_args!($($arg)*))
    };
}

#[macro_export]
macro_rules! trace2 {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::log(3, $indent, format_args!($($arg)*))
    };
}

#[macro_export]
macro_rules! error {
    ($indent:expr, $($arg:tt)*) => {
        $crate::log::error($indent, format_args!($($arg)*))
    };
}

#[macro_export]
macro_rules! progress {
    ($($arg:tt)*) => {
        $crate::log::progress(format_args!($($arg)*))
    };
}
