use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

/// Resolve a relative path against an absolute path.
/// If abs_path points to a file, resolve relative to its parent directory.
pub fn resolve_relative(relative_dir: &Path, abs_path: &Path) -> PathBuf {
    let base = if abs_path.is_file() {
        abs_path.parent().unwrap_or(abs_path)
    } else {
        abs_path
    };
    base.join(relative_dir)
}

/// Look up an executable name in `$PATH`. Returns the first hit that is a file.
/// Returns `None` if `$PATH` is unset or no directory contains it.
pub fn path_lookup(name: &str) -> Option<PathBuf> {
    let path_var = std::env::var_os("PATH")?;
    std::env::split_paths(&path_var)
        .map(|dir| dir.join(name))
        .find(|candidate| candidate.is_file())
}

/// Convert a string to bytes, optionally chopping trailing newline.
pub fn str_to_bytes(s: &str, chop_newline: bool) -> Vec<u8> {
    let s = if chop_newline && s.ends_with('\n') {
        &s[..s.len() - 1]
    } else {
        s
    };
    s.as_bytes().to_vec()
}

/// Create a temporary file with the given content and execute permissions.
/// The handle keeps the file alive.
pub fn make_tmp_file(content: &[u8]) -> Option<(PathBuf, tempfile::TempPath)> {
    let mut tmp = tempfile::NamedTempFile::new().ok()?;
    tmp.write_all(content).ok()?;
    let path = tmp.into_temp_path();
    let perms = fs::Permissions::from_mode(0o700);
    fs::set_permissions(&path, perms).ok()?;
    let path_buf = path.to_path_buf();
    Some((path_buf, path))
}

/// Create an empty temporary file with execute permissions.
/// The handle keeps the file alive.
pub fn make_empty_tmp_file() -> Option<(PathBuf, tempfile::TempPath)> {
    let tmp = tempfile::NamedTempFile::new().ok()?;
    let path = tmp.into_temp_path();
    let perms = fs::Permissions::from_mode(0o700);
    fs::set_permissions(&path, perms).ok()?;
    let path_buf = path.to_path_buf();
    Some((path_buf, path))
}

/// Truncate bytes in the middle if they exceed max_bytes.
pub fn truncated_bytes(data: &[u8], max_bytes: usize) -> Vec<u8> {
    if data.len() <= max_bytes {
        return data.to_vec();
    }
    let omission = b"\n{{ omitted for brevity }}\n";
    let available = max_bytes.saturating_sub(omission.len());
    let half = available / 2;
    let mut result = Vec::with_capacity(max_bytes);
    result.extend_from_slice(&data[..half]);
    result.extend_from_slice(omission);
    result.extend_from_slice(&data[data.len() - half..]);
    result
}
