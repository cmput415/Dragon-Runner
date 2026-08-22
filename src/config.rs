use std::collections::HashMap;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use colored::Colorize;
use serde::Deserialize;

use crate::cli::RunnerArgs;
use crate::error::{DragonError, Validate};
use crate::testfile::TestFile;
use crate::toolchain::{Step, ToolChain};
use crate::util::{path_lookup, resolve_relative};
use crate::{debug, error, trace, trace2};

/// Raw JSON shape of a config file, deserialized directly by serde.
#[derive(Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct RawConfig {
    #[serde(default)]
    test_dir: String,
    #[serde(default)]
    tested_executable_paths: HashMap<String, String>,
    #[serde(default)]
    runtimes: HashMap<String, String>,
    #[serde(default)]
    toolchains: HashMap<String, Vec<Step>>,
}

// ---------------------------------------------------------------------------
// SubPackage
// ---------------------------------------------------------------------------

/// Represents a set of tests in a directory.
#[derive(Debug, Clone)]
pub struct SubPackage {
    pub path: PathBuf,
    pub name: String,
    pub depth: usize,
    pub tests: Vec<Arc<TestFile>>,
}

impl SubPackage {
    pub fn new(path: &Path, depth: usize) -> Self {
        let name = path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        let tests = if path.is_dir() {
            Self::gather_tests(path)
        } else {
            vec![Arc::new(TestFile::new(path))]
        };

        Self {
            path: path.into(),
            name,
            depth,
            tests,
        }
    }

    fn gather_tests(dir: &Path) -> Vec<Arc<TestFile>> {
        let mut tests: Vec<Arc<TestFile>> = fs::read_dir(dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| TestFile::is_test(&e.path()))
            .map(|e| Arc::new(TestFile::new(&e.path())))
            .collect();
        tests.sort_by(|a, b| a.file.cmp(&b.file));
        tests
    }
}

impl Validate for SubPackage {
    fn validate(&self) -> Vec<DragonError> {
        self.tests.iter().flat_map(|t| t.validate()).collect()
    }
}

// ---------------------------------------------------------------------------
// Package
// ---------------------------------------------------------------------------

/// Represents a single test package.
#[derive(Debug, Clone)]
pub struct Package {
    pub path: PathBuf,
    pub name: String,
    pub n_tests: usize,
    pub subpackages: Vec<SubPackage>,
}

impl Package {
    pub fn new(path: &Path) -> Self {
        let name = path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        let mut pkg = Self {
            path: path.into(),
            name,
            n_tests: 0,
            subpackages: Vec::new(),
        };

        if path.is_dir() {
            pkg.gather_subpackages();
        } else {
            pkg.push_subpackage(SubPackage::new(path, 0));
        }

        pkg
    }

    fn push_subpackage(&mut self, spkg: SubPackage) {
        self.n_tests += spkg.tests.len();
        self.subpackages.push(spkg);
    }

    fn gather_subpackages(&mut self) {
        let top_level = SubPackage::new(&self.path, 0);
        if !top_level.tests.is_empty() {
            self.push_subpackage(top_level);
        }
        let path = self.path.clone();
        for spkg in Self::collect_subpackages_recursive(&path, 1) {
            self.push_subpackage(spkg);
        }
    }

    fn collect_subpackages_recursive(dir: &Path, depth: usize) -> Vec<SubPackage> {
        fs::read_dir(dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| {
                // Skip symlinks so a cycle can't blow the stack.
                let path = e.path();
                match fs::symlink_metadata(&path) {
                    Ok(md) => md.is_dir() && !md.file_type().is_symlink(),
                    Err(_) => false,
                }
            })
            .flat_map(|e| {
                let entry_path = e.path();
                let spkg = SubPackage::new(&entry_path, depth);
                let children = Self::collect_subpackages_recursive(&entry_path, depth + 1);
                let head = if spkg.tests.is_empty() {
                    None
                } else {
                    Some(spkg)
                };
                head.into_iter().chain(children)
            })
            .collect()
    }
}

impl Validate for Package {
    fn validate(&self) -> Vec<DragonError> {
        self.subpackages.iter().flat_map(|s| s.validate()).collect()
    }
}

/// Resolve an `exe` string from `testedExecutablePaths`.
///
/// - Bare names are resolved through `$PATH`.
/// - Anything containing a `/` is resolved as a filesystem path relative to
///   the config file's directory (absolute paths stay absolute).
fn resolve_exe_spec(spec: &str, config_path: &Path) -> PathBuf {
    if spec.contains('/') {
        resolve_relative(Path::new(spec), config_path)
    } else {
        PathBuf::from(spec)
    }
}

// ---------------------------------------------------------------------------
// Executable
// ---------------------------------------------------------------------------

/// Represents a tested executable with an optional runtime.
#[derive(Debug, Clone)]
pub struct Executable {
    pub id: String,
    pub exe_path: PathBuf,
    pub runtime: PathBuf,
}

impl Executable {
    pub fn new(id: &str, exe_path: PathBuf, runtime: PathBuf) -> Self {
        Self {
            id: id.into(),
            exe_path,
            runtime,
        }
    }

    /// Build environment variables needed for runtime library injection.
    /// Returns an empty map if no runtime is configured. Loader path/preload
    /// variables prepend to any existing caller value so we don't nuke it.
    pub fn runtime_env(&self) -> HashMap<String, String> {
        let mut env = HashMap::new();
        if self.runtime.as_os_str().is_empty() {
            return env;
        }
        let rt_dir = self
            .runtime
            .parent()
            .unwrap_or(Path::new(""))
            .display()
            .to_string();
        let rt_stem = self
            .runtime
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy();
        let rt_lib = rt_stem.strip_prefix("lib").unwrap_or(&rt_stem).to_string();
        let rt_str = self.runtime.display().to_string();

        if cfg!(target_os = "macos") {
            env.insert("DYLD_LIBRARY_PATH".into(), prepend_env("DYLD_LIBRARY_PATH", &rt_dir, ':'));
            env.insert("DYLD_INSERT_LIBRARIES".into(), prepend_env("DYLD_INSERT_LIBRARIES", &rt_str, ':'));
        } else {
            env.insert("LD_LIBRARY_PATH".into(), prepend_env("LD_LIBRARY_PATH", &rt_dir, ':'));
            env.insert("LD_PRELOAD".into(), prepend_env("LD_PRELOAD", &rt_str, ' '));
        }
        env.insert("RT_PATH".into(), rt_dir);
        env.insert("RT_LIB".into(), rt_lib);
        env
    }
}

fn prepend_env(name: &str, value: &str, sep: char) -> String {
    match std::env::var(name) {
        Ok(prev) if !prev.is_empty() => format!("{value}{sep}{prev}"),
        _ => value.to_string(),
    }
}

impl Validate for Executable {
    fn validate(&self) -> Vec<DragonError> {
        let mut errors = Vec::new();
        let exe_str = self.exe_path.to_string_lossy();
        let is_bare_name = !exe_str.contains('/');
        let found = if is_bare_name {
            path_lookup(&exe_str).is_some()
        } else {
            self.exe_path.exists()
        };
        if !found {
            errors.push(DragonError::MissingFile {
                path: self.exe_path.clone(),
                context: format!("Executable '{}'", self.id),
            });
        }
        if !self.runtime.as_os_str().is_empty() && !self.runtime.exists() {
            errors.push(DragonError::MissingFile {
                path: self.runtime.clone(),
                context: format!("Executable '{}' runtime", self.id),
            });
        }
        errors
    }
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/// In-memory representation of a JSON configuration file.
#[derive(Debug, Clone)]
pub struct Config {
    pub name: String,
    pub config_path: PathBuf,
    pub test_dir: PathBuf,
    pub executables: Vec<Executable>,
    pub toolchains: Vec<ToolChain>,
    pub packages: Vec<Package>,
    pub package_filter: String,
}

impl Config {
    fn new(
        config_path: &Path,
        raw: RawConfig,
        test_path: Option<&str>,
        package_filter: &str,
    ) -> Self {
        let abs_config =
            fs::canonicalize(config_path).unwrap_or_else(|_| config_path.to_path_buf());

        let name = config_path
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        let test_dir = resolve_relative(Path::new(&raw.test_dir), &abs_config);

        let executables = raw
            .tested_executable_paths
            .iter()
            .map(|(id, path_str)| {
                let exe_path = resolve_exe_spec(path_str, &abs_config);
                let runtime = raw
                    .runtimes
                    .get(id)
                    .map(|rt_path| {
                        let resolved = resolve_relative(Path::new(rt_path), &abs_config);
                        fs::canonicalize(&resolved).unwrap_or(resolved)
                    })
                    .unwrap_or_default();
                Executable::new(id, exe_path, runtime)
            })
            .collect();

        let toolchains = raw
            .toolchains
            .into_iter()
            .map(|(name, mut steps)| {
                for step in &mut steps {
                    // Resolve step exe paths relative to the config file, not the process cwd.
                    if !step.exe_raw.is_empty()
                        && !step.exe_raw.starts_with('$')
                        && step.exe_raw.contains('/')
                        && !Path::new(&step.exe_raw).is_absolute()
                    {
                        let resolved = resolve_relative(Path::new(&step.exe_raw), &abs_config);
                        step.exe_raw = resolved.to_string_lossy().into_owned();
                    }
                }
                ToolChain::new(&name, steps)
            })
            .collect();

        let packages = Self::gather_packages(&test_dir, test_path, &abs_config);

        Self {
            name,
            config_path: abs_config,
            test_dir,
            executables,
            toolchains,
            packages,
            package_filter: package_filter.into(),
        }
    }

    fn gather_packages(test_dir: &Path, test_path: Option<&str>, config_path: &Path) -> Vec<Package> {
        if let Some(pkg) = test_path.filter(|p| !p.is_empty()) {
            // --test-path is relative to the config file, matching how testDir resolves.
            let resolved = resolve_relative(Path::new(pkg), config_path);
            return vec![Package::new(&resolved)];
        }
        fs::read_dir(test_dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .map(|e| Package::new(&e.path()))
            .collect()
    }

    fn collect_errors(&self) -> Vec<DragonError> {
        let mut errors = Vec::new();
        if !self.test_dir.exists() {
            errors.push(DragonError::MissingTestDir {
                path: self.test_dir.clone(),
            });
        }
        if !self.package_filter.is_empty() {
            if let Err(e) = glob::Pattern::new(&self.package_filter.to_lowercase()) {
                errors.push(DragonError::InvalidPackageFilter {
                    pattern: self.package_filter.clone(),
                    reason: e.to_string(),
                });
            }
        }
        errors.extend(
            self.executables
                .iter()
                .flat_map(|e| e.validate())
                .chain(self.toolchains.iter().flat_map(|t| t.validate()))
                .chain(self.packages.iter().flat_map(|p| p.validate())),
        );
        errors
    }

    pub fn log_test_info(&self) {
        debug!(0, "\nPackages:");
        for pkg in &self.packages {
            debug!(2, "-- ({})", pkg.name);
            for spkg in &pkg.subpackages {
                trace!(4, "-- ({})", spkg.name);
                for test in &spkg.tests {
                    trace2!(6, "-- ({})", test.file);
                }
            }
        }
    }
}

impl fmt::Display for Config {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Debug::fmt(self, f)
    }
}

/// Load a config file or abort the process with a diagnostic on failure.
pub fn load_or_exit(path: &Path, args: Option<&RunnerArgs>) -> Config {
    match load_config(path, args) {
        Ok(c) => c,
        Err(errors) => {
            error!(0, "Found Config {} error(s):", errors.len());
            error!(0, "Parsed {} below:", path.display());
            for e in &errors {
                error!(0, "{}", format!("{e}").red());
            }
            std::process::exit(1);
        }
    }
}

/// Load and parse a JSON configuration file.
pub fn load_config(
    config_path: &Path,
    args: Option<&RunnerArgs>,
) -> Result<Config, Vec<DragonError>> {
    let path = config_path.to_path_buf();

    let content = fs::read_to_string(config_path)
        .map_err(|_| vec![DragonError::ConfigRead { path: path.clone() }])?;

    let raw: RawConfig = serde_json::from_str(&content).map_err(|e| {
        vec![DragonError::ConfigParse {
            path: path.clone(),
            reason: e.to_string(),
        }]
    })?;

    let test_path = args.and_then(|a| a.test_path.as_deref());
    let package_filter = args.and_then(|a| a.package_filter.as_deref()).unwrap_or("");

    let config = Config::new(config_path, raw, test_path, package_filter);
    let errors = config.collect_errors();
    if errors.is_empty() {
        Ok(config)
    } else {
        Err(errors)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn configs_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests")
            .join("configs")
    }

    fn config_path(name: &str) -> PathBuf {
        configs_dir().join(name)
    }

    #[test]
    fn test_valid_config() {
        let path = config_path("gccPassConfig.json");
        let config = load_config(&path, None).expect("config should load");

        assert!(
            config.test_dir.exists(),
            "test_dir should exist: {}",
            config.test_dir.display()
        );
        assert!(!config.packages.is_empty(), "should have packages");

        for pkg in &config.packages {
            assert!(
                !pkg.subpackages.is_empty(),
                "package {} should have subpackages",
                pkg.name
            );
            for spkg in &pkg.subpackages {
                assert!(
                    !spkg.tests.is_empty(),
                    "subpackage {} should have tests",
                    spkg.name
                );
            }
        }
    }

    #[test]
    fn test_package_filter() {
        let path = config_path("gccPassConfig.json");
        let config = load_config(&path, None).expect("config should load");

        let all_subpackages: Vec<String> = config
            .packages
            .iter()
            .flat_map(|pkg| pkg.subpackages.iter())
            .map(|spkg| spkg.path.display().to_string())
            .collect();

        assert!(!all_subpackages.is_empty(), "should have subpackages");

        let filter_pattern = "*ErrorPass*";
        let filtered: Vec<&String> = all_subpackages
            .iter()
            .filter(|path| {
                glob::Pattern::new(&filter_pattern.to_lowercase())
                    .map(|pat| pat.matches(&path.to_lowercase()))
                    .unwrap_or(false)
            })
            .collect();

        assert!(!filtered.is_empty(), "filter should match some subpackages");

        for path in &filtered {
            assert!(
                path.to_lowercase().contains("errorpass"),
                "filtered path should contain 'errorpass': {}",
                path
            );
        }
    }

    #[test]
    fn test_invalid_dir_config() {
        let path = config_path("invalidDirConfig.json");
        let errors = load_config(&path, None).unwrap_err();

        assert!(!errors.is_empty(), "should have errors for invalid dir");
        assert!(
            errors
                .iter()
                .any(|e| matches!(e, DragonError::MissingTestDir { .. })),
            "should have a MissingTestDir error"
        );
    }

    #[test]
    fn test_invalid_exe_config() {
        let path = config_path("invalidExeConfig.json");
        let errors = load_config(&path, None).unwrap_err();

        assert!(!errors.is_empty(), "should have errors for invalid exe");
        assert!(
            errors
                .iter()
                .any(|e| matches!(e, DragonError::MissingFile { .. })),
            "should have a MissingFile error"
        );
    }
}
