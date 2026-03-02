use std::path::Path;

use serde::Deserialize;

use crate::config::Executable;
use crate::error::{DragonError, Validate};

/// A single step in a toolchain (e.g., compile, link, run).
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Step {
    #[serde(rename = "exe", default)]
    pub exe_raw: String,
    #[serde(default)]
    pub args: Vec<String>,
    #[serde(default)]
    pub allow_error: bool,
    #[serde(rename = "usesInStr", default)]
    pub uses_ins: bool,
    #[serde(default)]
    pub uses_runtime: bool,
}

impl Step {
    /// Derive a human-readable step name from the raw exe string and the executable.
    pub fn display_name(&self, exe: &Executable) -> String {
        match self.exe_raw.as_str() {
            "$EXE" => exe.id.clone(),
            "$INPUT" => "run".to_string(),
            other => {
                // Use filename component for paths, bare name as-is
                Path::new(other)
                    .file_name()
                    .unwrap_or(other.as_ref())
                    .to_string_lossy()
                    .into_owned()
            }
        }
    }
}

impl Validate for Step {
    fn validate(&self) -> Vec<DragonError> {
        let mut errors = Vec::new();
        if self.exe_raw.is_empty() {
            errors.push(DragonError::Config(
                "Missing required field 'exe' in Step".into(),
            ));
        } else if !self.exe_raw.starts_with('$') && self.exe_raw.contains('/') {
            // Only check existence for paths (containing /), not bare names resolved via $PATH
            if !Path::new(&self.exe_raw).exists() {
                errors.push(DragonError::Config(format!(
                    "Cannot find exe '{}' in Step",
                    self.exe_raw
                )));
            }
        }
        errors
    }
}

/// An ordered sequence of Steps that form a compilation/execution pipeline.
#[derive(Debug, Clone)]
pub struct ToolChain {
    pub name: String,
    pub steps: Vec<Step>,
}

impl ToolChain {
    pub fn new(name: &str, steps: Vec<Step>) -> Self {
        Self { name: name.into(), steps }
    }

    pub fn len(&self) -> usize {
        self.steps.len()
    }

    pub fn is_empty(&self) -> bool {
        self.steps.is_empty()
    }

    pub fn iter(&self) -> std::slice::Iter<'_, Step> {
        self.steps.iter()
    }
}

impl Validate for ToolChain {
    fn validate(&self) -> Vec<DragonError> {
        self.steps.iter().flat_map(|s| s.validate()).collect()
    }
}
