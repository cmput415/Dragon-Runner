use std::collections::HashMap;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use crate::cli::RunnerArgs;
use crate::error::{DragonError, Validate};
use crate::log::log;
use crate::testfile::TestFile;
use crate::toolchain::ToolChain;
use crate::util::resolve_relative;

// ---------------------------------------------------------------------------
// SubPackage
// ---------------------------------------------------------------------------

/// Represents a set of tests in a directory.
#[derive(Debug, Clone)]
pub struct SubPackage {
    pub path: String,
    pub name: String,
    pub depth: usize,
    pub tests: Vec<Arc<TestFile>>,
}

impl SubPackage {
    pub fn new(path: &str, depth: usize) -> Self {
        let name = Path::new(path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        let tests = if Path::new(path).is_dir() {
            Self::gather_tests(path)
        } else {
            vec![Arc::new(TestFile::new(path))]
        };

        Self { path: path.into(), name, depth, tests }
    }

    fn gather_tests(dir: &str) -> Vec<Arc<TestFile>> {
        let mut tests: Vec<Arc<TestFile>> = fs::read_dir(dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| TestFile::is_test(&e.path()))
            .map(|e| Arc::new(TestFile::new(&e.path().to_string_lossy())))
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
    pub path: String,
    pub name: String,
    pub n_tests: usize,
    pub subpackages: Vec<SubPackage>,
}

impl Package {
    pub fn new(path: &str) -> Self {
        let name = Path::new(path)
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

        if Path::new(path).is_dir() {
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

    fn collect_subpackages_recursive(dir: &str, depth: usize) -> Vec<SubPackage> {
        fs::read_dir(dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .flat_map(|e| {
                let path_str = e.path().to_string_lossy().into_owned();
                let spkg = SubPackage::new(&path_str, depth);
                let children = Self::collect_subpackages_recursive(&path_str, depth + 1);
                let head = if spkg.tests.is_empty() { None } else { Some(spkg) };
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

// ---------------------------------------------------------------------------
// Executable
// ---------------------------------------------------------------------------

/// Represents a tested executable with an optional runtime.
#[derive(Debug, Clone)]
pub struct Executable {
    pub id: String,
    pub exe_path: String,
    pub runtime: String,
}

impl Executable {
    pub fn new(id: &str, exe_path: &str, runtime: &str) -> Self {
        Self { id: id.into(), exe_path: exe_path.into(), runtime: runtime.into() }
    }

    /// Build environment variables needed for runtime library injection.
    /// Returns an empty map if no runtime is configured.
    pub fn runtime_env(&self) -> HashMap<String, String> {
        let mut env = HashMap::new();
        if self.runtime.is_empty() {
            return env;
        }
        let rt = Path::new(&self.runtime);
        let rt_dir = rt.parent().unwrap_or(Path::new("")).to_string_lossy().into_owned();
        let rt_stem = rt.file_stem().unwrap_or_default().to_string_lossy();
        let rt_lib = rt_stem.strip_prefix("lib").unwrap_or(&rt_stem).to_string();

        if cfg!(target_os = "macos") {
            env.insert("DYLD_LIBRARY_PATH".into(), rt_dir.clone());
            env.insert("DYLD_INSERT_LIBRARIES".into(), self.runtime.clone());
        } else {
            env.insert("LD_LIBRARY_PATH".into(), rt_dir.clone());
            env.insert("LD_PRELOAD".into(), self.runtime.clone());
        }
        env.insert("RT_PATH".into(), rt_dir);
        env.insert("RT_LIB".into(), rt_lib);
        env
    }
}

impl Validate for Executable {
    fn validate(&self) -> Vec<DragonError> {
        let mut errors = Vec::new();
        if !Path::new(&self.exe_path).exists() {
            errors.push(DragonError::Config(format!(
                "Cannot find binary file: {} in Executable: {}", self.exe_path, self.id
            )));
        }
        if !self.runtime.is_empty() && !Path::new(&self.runtime).exists() {
            errors.push(DragonError::Config(format!(
                "Cannot find runtime file: {} in Executable: {}", self.runtime, self.id
            )));
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
    pub config_path: String,
    pub test_dir: String,
    pub executables: Vec<Executable>,
    pub solution_exe: Option<String>,
    pub toolchains: Vec<ToolChain>,
    pub packages: Vec<Package>,
    pub package_filter: String,
    pub errors: Vec<DragonError>,
}

impl Config {
    pub fn new(
        config_path: &str,
        config_data: &serde_json::Value,
        debug_package: Option<&str>,
        package_filter: &str,
    ) -> Self {
        let abs_config = fs::canonicalize(config_path)
            .unwrap_or_else(|_| PathBuf::from(config_path));
        let abs_config_str = abs_config.to_string_lossy().into_owned();

        let name = Path::new(config_path)
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        let test_dir_rel = config_data["testDir"].as_str().unwrap_or("");
        let test_dir = resolve_relative(test_dir_rel, &abs_config_str)
            .to_string_lossy()
            .into_owned();

        let executables = Self::parse_executables(
            config_data.get("testedExecutablePaths"),
            config_data.get("runtimes"),
            &abs_config_str,
        );
        let solution_exe = config_data["solutionExecutable"].as_str().map(Into::into);
        let toolchains = Self::parse_toolchains(config_data.get("toolchains"));
        let packages = Self::gather_packages(&test_dir, debug_package);

        let mut cfg = Self {
            name,
            config_path: abs_config_str,
            test_dir,
            executables,
            solution_exe,
            toolchains,
            packages,
            package_filter: package_filter.into(),
            errors: Vec::new(),
        };
        cfg.errors = cfg.collect_errors();
        cfg
    }

    fn parse_executables(
        exe_data: Option<&serde_json::Value>,
        runtime_data: Option<&serde_json::Value>,
        abs_config_path: &str,
    ) -> Vec<Executable> {
        let exe_map = match exe_data.and_then(|v| v.as_object()) {
            Some(m) => m,
            None => return Vec::new(),
        };
        let rt_map = runtime_data.and_then(|v| v.as_object());

        exe_map
            .iter()
            .map(|(id, path_val)| {
                let exe_path = resolve_relative(
                    path_val.as_str().unwrap_or(""),
                    abs_config_path,
                ).to_string_lossy().into_owned();

                let runtime = rt_map
                    .and_then(|rts| rts.get(id.as_str()))
                    .and_then(|v| v.as_str())
                    .map(|rt_path| {
                        let resolved = resolve_relative(rt_path, abs_config_path);
                        fs::canonicalize(&resolved)
                            .unwrap_or(resolved)
                            .to_string_lossy()
                            .into_owned()
                    })
                    .unwrap_or_default();

                Executable::new(id, &exe_path, &runtime)
            })
            .collect()
    }

    fn parse_toolchains(tc_data: Option<&serde_json::Value>) -> Vec<ToolChain> {
        tc_data
            .and_then(|v| v.as_object())
            .map(|map| {
                map.iter()
                    .map(|(name, steps)| {
                        ToolChain::new(name, steps.as_array().map(|a| a.as_slice()).unwrap_or(&[]))
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    fn gather_packages(test_dir: &str, debug_package: Option<&str>) -> Vec<Package> {
        if let Some(pkg) = debug_package.filter(|p| !p.is_empty()) {
            return vec![Package::new(pkg)];
        }
        fs::read_dir(test_dir)
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .map(|e| Package::new(&e.path().to_string_lossy()))
            .collect()
    }

    fn collect_errors(&self) -> Vec<DragonError> {
        let mut errors = Vec::new();
        if !Path::new(&self.test_dir).exists() {
            errors.push(DragonError::Config(format!(
                "Cannot find test directory: {}", self.test_dir
            )));
        }
        errors.extend(
            self.executables.iter().flat_map(|e| e.validate())
                .chain(self.toolchains.iter().flat_map(|t| t.validate()))
                .chain(self.packages.iter().flat_map(|p| p.validate()))
        );
        errors
    }

    pub fn log_test_info(&self) {
        log(1, 0, "\nPackages:");
        for pkg in &self.packages {
            log(1, 2, &format!("-- ({})", pkg.name));
            for spkg in &pkg.subpackages {
                log(2, 4, &format!("-- ({})", spkg.name));
                for test in &spkg.tests {
                    log(3, 6, &format!("-- ({})", test.file));
                }
            }
        }
    }
}

impl fmt::Display for Config {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f, "Config: {}", self.name)?;
        writeln!(f, "  testDir: {}", self.test_dir)?;
        writeln!(f, "  executables:")?;
        for exe in &self.executables {
            writeln!(f, "    - {} ({})", exe.id, exe.exe_path)?;
        }
        writeln!(f, "  toolchains:")?;
        for tc in &self.toolchains {
            writeln!(f, "    - {} ({} steps)", tc.name, tc.len())?;
        }
        writeln!(f, "  packages:")?;
        for pkg in &self.packages {
            write!(f, "    - {}", pkg.name)?;
        }
        Ok(())
    }
}

/// Load and parse a JSON configuration file.
pub fn load_config(config_path: &str, args: Option<&RunnerArgs>) -> Option<Config> {
    if !Path::new(config_path).exists() {
        return None;
    }

    let content = fs::read_to_string(config_path).ok().or_else(|| {
        log(0, 0, &format!("Config Error: Failed to parse config: {config_path}"));
        None
    })?;

    let config_data: serde_json::Value = serde_json::from_str(&content).ok().or_else(|| {
        log(0, 0, &format!("Config Error: Failed to parse config: {config_path}"));
        None
    })?;

    let debug_package = args
        .map(|a| a.debug_package.as_str())
        .filter(|p| !p.is_empty());
    let package_filter = args.map(|a| a.package_filter.as_str()).unwrap_or("");

    Some(Config::new(config_path, &config_data, debug_package, package_filter))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn configs_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests").join("configs")
    }

    fn config_path(name: &str) -> String {
        configs_dir().join(name).to_string_lossy().into_owned()
    }

    #[test]
    fn test_valid_config() {
        let path = config_path("gccPassConfig.json");
        let config = load_config(&path, None).expect("config should load");

        assert!(
            Path::new(&config.test_dir).exists(),
            "test_dir should exist: {}",
            config.test_dir
        );
        assert!(!config.packages.is_empty(), "should have packages");

        for pkg in &config.packages {
            assert!(!pkg.subpackages.is_empty(), "package {} should have subpackages", pkg.name);
            for spkg in &pkg.subpackages {
                assert!(!spkg.tests.is_empty(), "subpackage {} should have tests", spkg.name);
            }
        }

        assert!(config.errors.is_empty(), "should have no errors");
    }

    #[test]
    fn test_package_filter() {
        let path = config_path("gccPassConfig.json");
        let config = load_config(&path, None).expect("config should load");

        let all_subpackages: Vec<&str> = config
            .packages
            .iter()
            .flat_map(|pkg| pkg.subpackages.iter())
            .map(|spkg| spkg.path.as_str())
            .collect();

        assert!(!all_subpackages.is_empty(), "should have subpackages");

        let filter_pattern = "*ErrorPass*";
        let filtered: Vec<&&str> = all_subpackages
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
        let config = load_config(&path, None).expect("config should load");

        assert!(!config.errors.is_empty(), "should have errors for invalid dir");
        assert!(!Path::new(&config.test_dir).exists(), "test_dir should not exist");
    }

    #[test]
    fn test_invalid_exe_config() {
        let path = config_path("invalidExeConfig.json");
        let config = load_config(&path, None).expect("config should load");

        assert!(!config.errors.is_empty(), "should have errors for invalid exe");
        assert_eq!(config.executables.len(), 1);
        assert!(
            !Path::new(&config.executables[0].exe_path).exists(),
            "exe_path should not exist"
        );
    }
}
