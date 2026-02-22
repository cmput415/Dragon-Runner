use std::fs;
use std::io::{self, BufRead};
use std::path::Path;

use crate::error::{DragonError, Errors, Verifiable};
use crate::util::{file_to_bytes, str_to_bytes};

/// Represents a single test case file with parsed directives.
#[derive(Debug, Clone)]
pub struct TestFile {
    pub path: String,
    pub stem: String,
    pub extension: String,
    pub file: String,
    pub comment_syntax: String,
    pub expected_out: DirectiveResult,
    pub input_stream: DirectiveResult,
}

/// Result of parsing a directive — either successfully read bytes, or an error message.
#[derive(Debug, Clone)]
pub enum DirectiveResult {
    Ok(Vec<u8>),
    Err(String),
}

impl DirectiveResult {
    pub fn as_bytes(&self) -> &[u8] {
        match self {
            DirectiveResult::Ok(bytes) => bytes,
            DirectiveResult::Err(_) => b"",
        }
    }

    pub fn is_err(&self) -> bool {
        matches!(self, DirectiveResult::Err(_))
    }
}

impl TestFile {
    pub fn new(test_path: &str) -> Self {
        let path_obj = Path::new(test_path);
        let stem = path_obj.file_stem().unwrap_or_default().to_string_lossy().into_owned();
        let extension = path_obj
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
        self.expected_out.as_bytes()
    }

    pub fn get_input_stream(&self) -> &[u8] {
        self.input_stream.as_bytes()
    }

    /// Resolve inline vs file directives into final byte content.
    fn resolve_directive(
        test_path: &str,
        comment_syntax: &str,
        inline_dir: &str,
        file_dir: &str,
    ) -> DirectiveResult {
        let inline = Self::parse_directive(test_path, comment_syntax, inline_dir);
        let file_ref = Self::parse_directive(test_path, comment_syntax, file_dir);

        match (inline, file_ref) {
            (Some(Ok(_)), Some(Ok(_))) => DirectiveResult::Err(format!(
                "Directive Conflict for test {}: Supplied both {inline_dir} and {file_dir}",
                Path::new(test_path).file_name().unwrap_or_default().to_string_lossy(),
            )),

            (Some(Ok(bytes)), _) => DirectiveResult::Ok(bytes),
            (Some(Err(e)), _) => DirectiveResult::Err(e),

            (None, Some(Ok(ref_bytes))) => Self::read_referenced_file(test_path, file_dir, &ref_bytes),
            (None, Some(Err(e))) => DirectiveResult::Err(e),

            (None, None) => DirectiveResult::Ok(Vec::new()),
        }
    }

    /// Given file-reference bytes from a FILE directive, resolve and read the target file.
    fn read_referenced_file(test_path: &str, directive: &str, ref_bytes: &[u8]) -> DirectiveResult {
        let file_str = String::from_utf8_lossy(ref_bytes).trim().to_string();
        let parent = Path::new(test_path).parent().unwrap_or(Path::new(""));
        let full_path = parent.join(&file_str);

        if !full_path.exists() {
            return DirectiveResult::Err(format!(
                "Failed to locate path supplied to {directive}\n\tTest:{test_path}\n\tPath:{}\n",
                full_path.display(),
            ));
        }

        file_to_bytes(&full_path.to_string_lossy())
            .map(DirectiveResult::Ok)
            .unwrap_or_else(|| DirectiveResult::Err(format!(
                "Failed to convert file {} to bytes", full_path.display()
            )))
    }

    /// Scan a test file for lines matching `// DIRECTIVE:value` and collect the values.
    /// Returns None if no matches found.
    fn parse_directive(
        test_path: &str,
        comment_syntax: &str,
        directive: &str,
    ) -> Option<Result<Vec<u8>, String>> {
        let file = match fs::File::open(test_path) {
            Ok(f) => f,
            Err(_) => return Some(Err(format!(
                "Unknown error occurred while parsing testfile: {test_path}"
            ))),
        };

        let mut contents: Vec<u8> = Vec::new();
        let mut found_any = false;

        for line in io::BufReader::new(file).lines() {
            let line = match line {
                Ok(l) => l,
                Err(_) => return Some(Err(format!(
                    "Unknown error occurred while parsing testfile: {test_path}"
                ))),
            };

            match (line.find(comment_syntax), line.find(directive)) {
                (Some(c), Some(d)) if c <= d => {}
                _ => continue,
            }

            let rhs = match line.split_once(directive) {
                Some((_, rhs)) => rhs,
                None => continue,
            };

            if found_any {
                contents.push(b'\n');
            }
            contents.extend_from_slice(&str_to_bytes(rhs, true));
            found_any = true;
        }

        found_any.then(|| Ok(contents))
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

impl Verifiable for TestFile {
    fn verify(&self) -> Errors {
        let mut ec = Errors::new();
        if let DirectiveResult::Err(msg) = &self.expected_out {
            ec.push(DragonError::TestFile(msg.clone()));
        }
        if let DirectiveResult::Err(msg) = &self.input_stream {
            ec.push(DragonError::TestFile(msg.clone()));
        }
        ec
    }
}
