use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use crate::cli::RunnerArgs;
use crate::error::{Error, ErrorCollection, Verifiable};
use crate::log::log;
use crate::testfile::TestFile;
use crate::toolchain::ToolChain;
use crate::util::resolve_relative;

/// Represents a set of tests in a directory.
#[derive(Debug, Clone)]
pub struct SubPackage {
    pub path: String,
    pub name: String,
    pub tests: Vec<TestFile>,
}

impl SubPackage {
    pub fn new(path: &str) -> Self {
        let name = Path::new(path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        let tests = if Path::new(path).is_dir() {
            Self::gather_tests(path)
        } else {
            vec![TestFile::new(path)]
        };

        Self {
            path: path.to_string(),
            name,
            tests,
        }
    }

    fn gather_tests(dir: &str) -> Vec<TestFile> {
        let mut tests = Vec::new();
        if let Ok(entries) = fs::read_dir(dir) {
            for entry in entries.flatten() {
                let entry_path = entry.path();
                if TestFile::is_test(&entry_path) {
                    tests.push(TestFile::new(&entry_path.to_string_lossy()));
                }
            }
        }
        tests.sort_by(|a, b| a.file.cmp(&b.file));
        tests
    }
}

impl Verifiable for SubPackage {
    fn verify(&self) -> ErrorCollection {
        let mut ec = ErrorCollection::new();
        for test in &self.tests {
            ec.extend(&test.verify());
        }
        ec
    }
}

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
            path: path.to_string(),
            name,
            n_tests: 0,
            subpackages: Vec::new(),
        };

        if Path::new(path).is_dir() {
            pkg.gather_subpackages();
        } else {
            let spkg = SubPackage::new(path);
            pkg.add_subpackage(spkg);
        }

        pkg
    }

    fn add_subpackage(&mut self, spkg: SubPackage) {
        self.n_tests += spkg.tests.len();
        self.subpackages.push(spkg);
    }

    fn gather_subpackages(&mut self) {
        // Check for top-level tests in the package dir itself
        let top_level = SubPackage::new(&self.path);
        if !top_level.tests.is_empty() {
            self.add_subpackage(top_level);
        }

        // Collect all subdirectory subpackages first, then add them
        let path = self.path.clone();
        let collected = Self::collect_subpackages(&path);
        for spkg in collected {
            self.add_subpackage(spkg);
        }
    }

    fn collect_subpackages(dir: &str) -> Vec<SubPackage> {
        let mut result = Vec::new();
        if let Ok(entries) = fs::read_dir(dir) {
            for entry in entries.flatten() {
                let entry_path = entry.path();
                if entry_path.is_dir() {
                    let spkg = SubPackage::new(&entry_path.to_string_lossy());
                    if !spkg.tests.is_empty() {
                        result.push(spkg);
                    }
                    result.extend(Self::collect_subpackages(&entry_path.to_string_lossy()));
                }
            }
        }
        result
    }
}

impl Verifiable for Package {
    fn verify(&self) -> ErrorCollection {
        let mut ec = ErrorCollection::new();
        for spkg in &self.subpackages {
            ec.extend(&spkg.verify());
        }
        ec
    }
}

/// Represents a tested executable with an optional runtime.
#[derive(Debug, Clone)]
pub struct Executable {
    pub id: String,
    pub exe_path: String,
    pub runtime: String,
}

impl Executable {
    pub fn new(id: &str, exe_path: &str, runtime: &str) -> Self {
        Self {
            id: id.to_string(),
            exe_path: exe_path.to_string(),
            runtime: runtime.to_string(),
        }
    }

    /// Set environment variables for runtime library injection.
    pub fn source_env(&self) {
        if self.runtime.is_empty() {
            return;
        }
        let runtime_path = Path::new(&self.runtime);
        let runtime_dir = runtime_path
            .parent()
            .unwrap_or(Path::new(""))
            .to_string_lossy()
            .into_owned();
        let rt_filename = runtime_path
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();

        // Strip leading "lib" prefix for linker flag
        let rt_lib = if rt_filename.starts_with("lib") {
            rt_filename[3..].to_string()
        } else {
            rt_filename
        };

        if cfg!(target_os = "macos") {
            env::set_var("DYLD_LIBRARY_PATH", &runtime_dir);
            env::set_var("DYLD_INSERT_LIBRARIES", &self.runtime);
        } else {
            env::set_var("LD_LIBRARY_PATH", &runtime_dir);
            env::set_var("LD_PRELOAD", &self.runtime);
        }

        env::set_var("RT_PATH", &runtime_dir);
        env::set_var("RT_LIB", &rt_lib);
    }
}

impl Verifiable for Executable {
    fn verify(&self) -> ErrorCollection {
        let mut errors = ErrorCollection::new();
        if !Path::new(&self.exe_path).exists() {
            errors.add(Error::Config(format!(
                "Cannot find binary file: {} in Executable: {}",
                self.exe_path, self.id
            )));
        }
        if !self.runtime.is_empty() && !Path::new(&self.runtime).exists() {
            errors.add(Error::Config(format!(
                "Cannot find runtime file: {} in Executable: {}",
                self.runtime, self.id
            )));
        }
        errors
    }
}

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
    pub error_collection: ErrorCollection,
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

        let test_dir_rel = config_data
            .get("testDir")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let test_dir = resolve_relative(test_dir_rel, &abs_config_str)
            .to_string_lossy()
            .into_owned();

        let executables = Self::parse_executables(
            config_data.get("testedExecutablePaths"),
            config_data.get("runtimes"),
            &abs_config_str,
        );

        let solution_exe = config_data
            .get("solutionExecutable")
            .and_then(|v| v.as_str())
            .map(String::from);

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
            package_filter: package_filter.to_string(),
            error_collection: ErrorCollection::new(),
        };
        cfg.error_collection = cfg.do_verify();
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
                let path_str = path_val.as_str().unwrap_or("");
                let exe_path = resolve_relative(path_str, abs_config_path)
                    .to_string_lossy()
                    .into_owned();

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
        let tc_map = match tc_data.and_then(|v| v.as_object()) {
            Some(m) => m,
            None => return Vec::new(),
        };
        tc_map
            .iter()
            .map(|(name, steps_val)| {
                let steps = steps_val
                    .as_array()
                    .map(|arr| arr.as_slice())
                    .unwrap_or(&[]);
                ToolChain::new(name, steps)
            })
            .collect()
    }

    fn gather_packages(test_dir: &str, debug_package: Option<&str>) -> Vec<Package> {
        if let Some(debug_pkg) = debug_package {
            if !debug_pkg.is_empty() {
                return vec![Package::new(debug_pkg)];
            }
        }

        let mut packages = Vec::new();
        if let Ok(entries) = fs::read_dir(test_dir) {
            for entry in entries.flatten() {
                let entry_path = entry.path();
                if entry_path.is_dir() {
                    packages.push(Package::new(&entry_path.to_string_lossy()));
                }
            }
        }
        packages
    }

    fn do_verify(&self) -> ErrorCollection {
        let mut ec = ErrorCollection::new();
        if !Path::new(&self.test_dir).exists() {
            // Use the raw testDir value from config for the error message
            ec.add(Error::Config(format!(
                "Cannot find test directory: {}",
                self.test_dir
            )));
        }
        for exe in &self.executables {
            ec.extend(&exe.verify());
        }
        for tc in &self.toolchains {
            ec.extend(&tc.verify());
        }
        for pkg in &self.packages {
            ec.extend(&pkg.verify());
        }
        ec
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

/// Load and parse a JSON configuration file.
pub fn load_config(config_path: &str, args: Option<&RunnerArgs>) -> Option<Config> {
    if !Path::new(config_path).exists() {
        return None;
    }

    let content = match fs::read_to_string(config_path) {
        Ok(c) => c,
        Err(_) => {
            log(0, 0, &format!("Config Error: Failed to parse config: {config_path}"));
            return None;
        }
    };

    let config_data: serde_json::Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(_) => {
            log(0, 0, &format!("Config Error: Failed to parse config: {config_path}"));
            return None;
        }
    };

    let debug_package = args
        .and_then(|a| {
            if a.debug_package.is_empty() {
                None
            } else {
                Some(a.debug_package.as_str())
            }
        });
    let package_filter = args.map(|a| a.package_filter.as_str()).unwrap_or("");

    Some(Config::new(config_path, &config_data, debug_package, package_filter))
}
