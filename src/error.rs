use std::path::PathBuf;

use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum DragonError {
    #[error("Failed to read config file: {path}")]
    ConfigRead { path: PathBuf },

    #[error("Failed to parse config file {path}: {reason}")]
    ConfigParse { path: PathBuf, reason: String },

    #[error("Missing file: {path} ({context})")]
    MissingFile { path: PathBuf, context: String },

    #[error("Missing test directory: {path}")]
    MissingTestDir { path: PathBuf },

    #[error("Missing required field '{field}' in {context}")]
    MissingField { field: String, context: String },

    #[error("Directive conflict in {test}: both {inline} and {file_dir} supplied")]
    DirectiveConflict {
        test: String,
        inline: String,
        file_dir: String,
    },

    #[error("Failed to read test file: {path}")]
    TestFileRead { path: PathBuf },

    #[error("Referenced file not found: {path} (directive {directive} in test {test})")]
    ReferencedFileNotFound {
        path: PathBuf,
        directive: String,
        test: PathBuf,
    },

    #[error("Failed to read referenced file: {path}")]
    ReferencedFileRead { path: PathBuf },
}

pub trait Validate {
    fn validate(&self) -> Vec<DragonError>;
}
