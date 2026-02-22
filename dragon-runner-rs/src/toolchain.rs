use std::path::Path;

use crate::error::{Error, ErrorCollection, Verifiable};

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
            name: data
                .get("stepName")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            exe_path: data
                .get("executablePath")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            arguments: data
                .get("arguments")
                .and_then(|v| v.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_default(),
            output: data
                .get("output")
                .and_then(|v| v.as_str())
                .map(String::from),
            allow_error: data
                .get("allowError")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            uses_ins: data
                .get("usesInStr")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            uses_runtime: data
                .get("usesRuntime")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        }
    }
}

impl Verifiable for Step {
    fn verify(&self) -> ErrorCollection {
        let mut errors = ErrorCollection::new();
        if self.name.is_empty() {
            errors.add(Error::Config(format!(
                "Missing required filed 'stepName' in Step {}",
                self.name
            )));
        }
        if self.exe_path.is_empty() {
            errors.add(Error::Config(format!(
                "Missing required field 'exe_path' in Step: {}",
                self.name
            )));
        } else if !self.exe_path.starts_with('$') && !Path::new(&self.exe_path).exists() {
            errors.add(Error::Config(format!(
                "Cannot find exe_path '{}' in Step: {}",
                self.exe_path, self.name
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
        let steps = steps_data.iter().map(Step::from_json).collect();
        Self {
            name: name.to_string(),
            steps,
        }
    }

    pub fn len(&self) -> usize {
        self.steps.len()
    }

    pub fn iter(&self) -> std::slice::Iter<'_, Step> {
        self.steps.iter()
    }
}

impl Verifiable for ToolChain {
    fn verify(&self) -> ErrorCollection {
        let mut errors = ErrorCollection::new();
        for step in &self.steps {
            errors.extend(&step.verify());
        }
        errors
    }
}
