use std::fmt;

#[derive(Debug, Clone)]
pub enum Error {
    Config(String),
    TestFile(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Config(msg) => write!(f, "Config Error: {msg}"),
            Error::TestFile(msg) => write!(f, "Testfile Error: {msg}"),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct ErrorCollection {
    pub errors: Vec<Error>,
}

impl ErrorCollection {
    pub fn new() -> Self {
        Self { errors: Vec::new() }
    }

    pub fn has_errors(&self) -> bool {
        !self.errors.is_empty()
    }

    pub fn add(&mut self, error: Error) {
        self.errors.push(error);
    }

    pub fn extend(&mut self, other: &ErrorCollection) {
        self.errors.extend(other.errors.iter().cloned());
    }

    pub fn extend_errors(&mut self, errors: &[Error]) {
        self.errors.extend(errors.iter().cloned());
    }

    pub fn len(&self) -> usize {
        self.errors.len()
    }

    pub fn is_empty(&self) -> bool {
        self.errors.is_empty()
    }
}

impl fmt::Display for ErrorCollection {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (i, err) in self.errors.iter().enumerate() {
            if i > 0 {
                writeln!(f)?;
            }
            write!(f, "{err}")?;
        }
        Ok(())
    }
}

pub trait Verifiable {
    fn verify(&self) -> ErrorCollection;
}
