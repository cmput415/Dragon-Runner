use std::fs;
use std::io::{self, BufRead};
use std::path::Path;

use crate::error::{Error, ErrorCollection, Verifiable};
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
        let stem = path_obj
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();
        let extension = path_obj
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy()))
            .unwrap_or_default();
        let file = format!("{}{}", stem, extension);
        let comment_syntax = "//".to_string();

        let expected_out = Self::get_content_static(
            test_path,
            &comment_syntax,
            "CHECK:",
            "CHECK_FILE:",
        );
        let input_stream = Self::get_content_static(
            test_path,
            &comment_syntax,
            "INPUT:",
            "INPUT_FILE:",
        );

        Self {
            path: test_path.to_string(),
            stem,
            extension,
            file,
            comment_syntax,
            expected_out,
            input_stream,
        }
    }

    pub fn get_expected_out(&self) -> &[u8] {
        self.expected_out.as_bytes()
    }

    pub fn get_input_stream(&self) -> &[u8] {
        self.input_stream.as_bytes()
    }

    /// Generic method to get content based on inline and file directives.
    fn get_content_static(
        test_path: &str,
        comment_syntax: &str,
        inline_directive: &str,
        file_directive: &str,
    ) -> DirectiveResult {
        let inline_contents = Self::get_directive_contents(test_path, comment_syntax, inline_directive);
        let file_contents = Self::get_directive_contents(test_path, comment_syntax, file_directive);

        match (&inline_contents, &file_contents) {
            // Both directives present — conflict
            (Some(Ok(_)), Some(Ok(_))) => DirectiveResult::Err(format!(
                "Directive Conflict for test {}: Supplied both {} and {}",
                Path::new(test_path)
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy(),
                inline_directive,
                file_directive,
            )),

            // Only inline directive
            (Some(Ok(bytes)), _) => DirectiveResult::Ok(bytes.clone()),
            (Some(Err(e)), _) => DirectiveResult::Err(e.clone()),

            // Only file directive — read referenced file
            (None, Some(Ok(file_ref_bytes))) => {
                let file_str = String::from_utf8_lossy(file_ref_bytes).trim().to_string();
                let parent = Path::new(test_path).parent().unwrap_or(Path::new(""));
                let full_path = parent.join(&file_str);

                if !full_path.exists() {
                    return DirectiveResult::Err(format!(
                        "Failed to locate path supplied to {}\n\tTest:{}\n\tPath:{}\n",
                        file_directive,
                        test_path,
                        full_path.display(),
                    ));
                }

                match file_to_bytes(&full_path.to_string_lossy()) {
                    Some(bytes) => DirectiveResult::Ok(bytes),
                    None => DirectiveResult::Err(format!(
                        "Failed to convert file {} to bytes",
                        full_path.display()
                    )),
                }
            }
            (None, Some(Err(e))) => DirectiveResult::Err(e.clone()),

            // Neither directive — empty
            (None, None) => DirectiveResult::Ok(Vec::new()),
        }
    }

    /// Parse directive contents from the test file.
    /// Returns None if no directive found, Some(Ok(bytes)) for content,
    /// or Some(Err(msg)) on parse error.
    fn get_directive_contents(
        test_path: &str,
        comment_syntax: &str,
        directive_prefix: &str,
    ) -> Option<Result<Vec<u8>, String>> {
        let file = match fs::File::open(test_path) {
            Ok(f) => f,
            Err(_) => {
                return Some(Err(format!(
                    "Unkown error occured while parsing testfile: {}",
                    test_path
                )));
            }
        };

        let reader = io::BufReader::new(file);
        let mut contents: Vec<u8> = Vec::new();
        let mut first_match = true;

        for line_result in reader.lines() {
            let line = match line_result {
                Ok(l) => l,
                Err(_) => {
                    return Some(Err(format!(
                        "Unkown error occured while parsing testfile: {}",
                        test_path
                    )));
                }
            };

            let comment_index = match line.find(comment_syntax) {
                Some(i) => i,
                None => continue,
            };
            let directive_index = match line.find(directive_prefix) {
                Some(i) => i,
                None => continue,
            };

            // Comment must appear before directive
            if comment_index > directive_index {
                continue;
            }

            // Extract the right-hand side after the directive
            let rhs = match line.split_once(directive_prefix) {
                Some((_, rhs)) => rhs,
                None => continue,
            };

            let rhs_bytes = str_to_bytes(rhs, true);

            if !first_match {
                contents.push(b'\n');
            }
            contents.extend_from_slice(&rhs_bytes);
            first_match = false;
        }

        if first_match {
            // No matches found
            None
        } else {
            Some(Ok(contents))
        }
    }

    /// Check if a path is a valid test file (not hidden, not .out/.ins extension).
    pub fn is_test(test_path: &Path) -> bool {
        if !test_path.is_file() {
            return false;
        }
        let name = test_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy();
        if name.starts_with('.') {
            return false;
        }
        let ext = test_path
            .extension()
            .unwrap_or_default()
            .to_string_lossy();
        ext != "out" && ext != "ins"
    }
}

impl Verifiable for TestFile {
    fn verify(&self) -> ErrorCollection {
        let mut ec = ErrorCollection::new();
        if let DirectiveResult::Err(msg) = &self.expected_out {
            ec.add(Error::TestFile(msg.clone()));
        }
        if let DirectiveResult::Err(msg) = &self.input_stream {
            ec.add(Error::TestFile(msg.clone()));
        }
        ec
    }
}
