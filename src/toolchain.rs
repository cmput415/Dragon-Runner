use std::path::Path;

use crate::error::{DragonError, Validate};

/// A single step in a toolchain (e.g., compile, link, run).
#[derive(Debug, Clone)]
pub struct Step {
    pub name: String,
    pub exe_path: String,
    pub arguments: Vec<String>,
    pub output: Option<String>,
    pub allow_error: bool,
    pub uses_ins: bool,
    pub uses_runtime: bool,
}

impl Step {
    pub fn from_json(data: &serde_json::Value) -> Self {
        Self {
            name: data["stepName"].as_str().unwrap_or("").into(),
            exe_path: data["executablePath"].as_str().unwrap_or("").into(),
            arguments: data
                .get("arguments")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str().map(Into::into)).collect())
                .unwrap_or_default(),
            output: data.get("output").and_then(|v| v.as_str()).map(Into::into),
            allow_error: data["allowError"].as_bool().unwrap_or(false),
            uses_ins: data["usesInStr"].as_bool().unwrap_or(false),
            uses_runtime: data["usesRuntime"].as_bool().unwrap_or(false),
        }
    }
}

impl Validate for Step {
    fn validate(&self) -> Vec<DragonError> {
        let mut errors = Vec::new();
        if self.name.is_empty() {
            errors.push(DragonError::Config(format!(
                "Missing required field 'stepName' in Step {}", self.name
            )));
        }
        if self.exe_path.is_empty() {
            errors.push(DragonError::Config(format!(
                "Missing required field 'exe_path' in Step: {}", self.name
            )));
        } else if !self.exe_path.starts_with('$') && !Path::new(&self.exe_path).exists() {
            errors.push(DragonError::Config(format!(
                "Cannot find exe_path '{}' in Step: {}", self.exe_path, self.name
            )));
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
    pub fn new(name: &str, steps_data: &[serde_json::Value]) -> Self {
        Self {
            name: name.into(),
            steps: steps_data.iter().map(Step::from_json).collect(),
        }
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
