use std::fmt;
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum DragonError {
    #[error("Config Error: {0}")]
    Config(String),
    #[error("Testfile Error: {0}")]
    TestFile(String),
}

/// Collect validation errors from config, toolchains, test files, etc.
/// Just a thin newtype over Vec so we can impl Display.
#[derive(Debug, Clone, Default)]
pub struct Errors(pub Vec<DragonError>);

impl Errors {
    pub fn new() -> Self {
        Self(Vec::new())
    }

    pub fn has_errors(&self) -> bool {
        !self.0.is_empty()
    }

    pub fn push(&mut self, error: DragonError) {
        self.0.push(error);
    }

    pub fn extend(&mut self, other: &Errors) {
        self.0.extend_from_slice(&other.0);
    }

    pub fn len(&self) -> usize {
        self.0.len()
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

impl fmt::Display for Errors {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (i, err) in self.0.iter().enumerate() {
            if i > 0 {
                writeln!(f)?;
            }
            write!(f, "{err}")?;
        }
        Ok(())
    }
}

pub trait Verifiable {
    fn verify(&self) -> Errors;
}
