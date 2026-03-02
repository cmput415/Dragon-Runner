use std::fs;
use std::io::{self, BufRead};
use std::path::{Path, PathBuf};

use crate::error::{DragonError, Validate};
use crate::util::str_to_bytes;

/// Result of parsing a directive — either successfully read bytes, or an error message.
pub type DirectiveResult = Result<Vec<u8>, String>;

/// Represents a single test case file with parsed directives.
#[derive(Debug, Clone)]
pub struct TestFile {
    pub path: PathBuf,
    pub stem: String,
    pub extension: String,
    pub file: String,
    pub comment_syntax: String,
    pub expected_out: DirectiveResult,
    pub input_stream: DirectiveResult,
}

impl TestFile {
    pub fn new(test_path: &Path) -> Self {
        let stem = test_path.file_stem().unwrap_or_default().to_string_lossy().into_owned();
        let extension = test_path
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy()))
            .unwrap_or_default();
        let file = format!("{stem}{extension}");
        let comment_syntax = "//".to_string();

        let expected_out = Self::resolve_directive(test_path, &comment_syntax, "CHECK:", "CHECK_FILE:");
        let input_stream = Self::resolve_directive(test_path, &comment_syntax, "INPUT:", "INPUT_FILE:");

        Self { path: test_path.into(), stem, extension, file, comment_syntax, expected_out, input_stream }
    }

    pub fn get_expected_out(&self) -> &[u8] {
        self.expected_out.as_deref().unwrap_or(b"")
    }

    pub fn get_input_stream(&self) -> &[u8] {
        self.input_stream.as_deref().unwrap_or(b"")
    }

    /// Resolve inline vs file directives into final byte content.
    fn resolve_directive(
        test_path: &Path,
        comment_syntax: &str,
        inline_dir: &str,
        file_dir: &str,
    ) -> DirectiveResult {
        let inline = Self::parse_directive(test_path, comment_syntax, inline_dir);
        let file_ref = Self::parse_directive(test_path, comment_syntax, file_dir);

        match (inline, file_ref) {
            (Some(Ok(_)), Some(Ok(_))) => Err(format!(
                "Directive Conflict for test {}: Supplied both {inline_dir} and {file_dir}",
                test_path.file_name().unwrap_or_default().to_string_lossy(),
            )),
            (Some(Ok(bytes)), _) => Ok(bytes),
            (Some(Err(e)), _) => Err(e),
            (None, Some(Ok(ref_bytes))) => Self::read_referenced_file(test_path, file_dir, &ref_bytes),
            (None, Some(Err(e))) => Err(e),
            (None, None) => Ok(Vec::new()),
        }
    }

    /// Given file-reference bytes from a FILE directive, resolve and read the target file.
    fn read_referenced_file(test_path: &Path, directive: &str, ref_bytes: &[u8]) -> DirectiveResult {
        let file_str = String::from_utf8_lossy(ref_bytes).trim().to_string();
        let parent = test_path.parent().unwrap_or(Path::new(""));
        let full_path = parent.join(&file_str);

        if !full_path.exists() {
            return Err(format!(
                "Failed to locate path supplied to {directive}\n\tTest:{}\n\tPath:{}\n",
                test_path.display(),
                full_path.display(),
            ));
        }

        fs::read(&full_path)
            .map_err(|_| format!("Failed to read file {}", full_path.display()))
    }

    /// Scan a test file for lines matching `// DIRECTIVE:value` and collect the values.
    /// Returns None if no matches found.
    fn parse_directive(
        test_path: &Path,
        comment_syntax: &str,
        directive: &str,
    ) -> Option<DirectiveResult> {
        let err = || format!("Unknown error occurred while parsing testfile: {}", test_path.display());

        let file = match fs::File::open(test_path) {
            Ok(f) => f,
            Err(_) => return Some(Err(err())),
        };

        let values: Result<Vec<Vec<u8>>, String> = io::BufReader::new(file)
            .lines()
            .map(|line| line.map_err(|_| err()))
            .filter_map(|line| {
                let line = match line {
                    Ok(l) => l,
                    Err(e) => return Some(Err(e)),
                };
                let comment_pos = line.find(comment_syntax)?;
                let directive_pos = line.find(directive)?;
                if comment_pos > directive_pos {
                    return None;
                }
                let (_, rhs) = line.split_once(directive)?;
                Some(Ok(str_to_bytes(rhs, true)))
            })
            .collect();

        match values {
            Err(e) => Some(Err(e)),
            Ok(parts) if parts.is_empty() => None,
            Ok(parts) => Some(Ok(parts.join(&b'\n'))),
        }
    }

    /// Check if a path is a valid test file (not hidden, not .out/.ins extension).
    pub fn is_test(path: &Path) -> bool {
        path.is_file()
            && !path.file_name().unwrap_or_default().to_string_lossy().starts_with('.')
            && !matches!(
                path.extension().and_then(|e| e.to_str()),
                Some("out" | "ins")
            )
    }
}

impl Validate for TestFile {
    fn validate(&self) -> Vec<DragonError> {
        [&self.expected_out, &self.input_stream]
            .into_iter()
            .filter_map(|r| r.as_ref().err())
            .map(|msg| DragonError::TestFile(msg.clone()))
            .collect()
    }
}
