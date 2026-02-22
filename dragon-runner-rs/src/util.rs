use std::path::{Path, PathBuf};
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;

/// Resolve a relative path against an absolute path.
/// If abs_path points to a file, resolve relative to its parent directory.
pub fn resolve_relative(relative_dir: &str, abs_path: &str) -> PathBuf {
    let abs = Path::new(abs_path);
    let base = if abs.is_file() {
        abs.parent().unwrap_or(abs)
    } else {
        abs
    };
    base.join(relative_dir)
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

/// Read a file as bytes, returning None on error.
pub fn file_to_bytes(path: &str) -> Option<Vec<u8>> {
    fs::read(path).ok()
}

/// Read a file as a UTF-8 string, returning None on error.
pub fn file_to_str(path: &str) -> Option<String> {
    fs::read_to_string(path).ok()
}

/// Create a temporary file with the given content and execute permissions.
/// Returns the path to the temp file, or None on error.
pub fn make_tmp_file(content: &[u8]) -> Option<String> {
    let mut tmp = tempfile::NamedTempFile::new().ok()?;
    tmp.write_all(content).ok()?;
    let path = tmp.into_temp_path();
    // Set execute permissions
    let perms = fs::Permissions::from_mode(0o700);
    fs::set_permissions(&path, perms).ok()?;
    let path_str = path.to_string_lossy().to_string();
    // Leak the temp path so it persists (matches Python behavior)
    std::mem::forget(path);
    path_str.into()
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

/// Convert bytes to string with lossy UTF-8 fallback.
pub fn bytes_to_str(data: &[u8]) -> String {
    String::from_utf8_lossy(data).into_owned()
}
