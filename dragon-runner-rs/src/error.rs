use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum DragonError {
    #[error("Config Error: {0}")]
    Config(String),
    #[error("Testfile Error: {0}")]
    TestFile(String),
}

pub trait Validate {
    fn validate(&self) -> Vec<DragonError>;
}
