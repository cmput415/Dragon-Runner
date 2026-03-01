use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::Path;
use std::process;
use std::sync::{Arc, LazyLock};
use std::time::{Duration, Instant};

use regex::Regex;
use wait_timeout::ChildExt;

static ENV_VAR_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\$(\w+)|\$\{(\w+)\}").unwrap());
static ERROR_KIND_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)(\w+Error)").unwrap());
static ERROR_LINE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)on\s+Line\s+(\d+)").unwrap());

use crate::config::Executable;
use crate::testfile::TestFile;
use crate::toolchain::{Step, ToolChain};
use crate::util::{file_to_bytes, make_tmp_file};

/// Reserved exit code for valgrind leak detection.
pub const VALGRIND_EXIT_CODE: i32 = 111;

/// Magic parameter values substituted into toolchain step arguments.
pub struct MagicParams {
    pub exe_path: String,
    pub input_file: String,
    pub output_file: Option<String>,
}

/// A resolved command ready to execute.
pub struct Command {
    pub args: Vec<String>,
    pub cmd: String,
}

impl Command {
    pub fn new(args: Vec<String>) -> Self {
        let cmd = args.first().cloned().unwrap_or_default();
        Self { args, cmd }
    }
}

/// Result of executing a single subprocess.
pub struct CommandResult {
    pub cmd: String,
    pub exit_status: i32,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub time: f64,
    pub timed_out: bool,
}

impl CommandResult {
    pub fn new(cmd: &str) -> Self {
        Self {
            cmd: cmd.to_string(),
            exit_status: 0,
            stdout: Vec::new(),
            stderr: Vec::new(),
            time: 0.0,
            timed_out: false,
        }
    }
}

/// Result of running a complete test case through a toolchain.
pub struct TestResult {
    pub test: Arc<TestFile>,
    pub did_pass: bool,
    pub did_timeout: bool,
    pub error_test: bool,
    pub memory_leak: bool,
    pub command_history: Vec<CommandResult>,
    pub gen_output: Option<Vec<u8>>,
    pub time: Option<f64>,
    pub failing_step: Option<String>,
}

impl TestResult {
    pub fn new(test: Arc<TestFile>) -> Self {
        Self {
            test,
            did_pass: false,
            did_timeout: false,
            error_test: false,
            memory_leak: false,
            command_history: Vec::new(),
            gen_output: None,
            time: None,
            failing_step: None,
        }
    }
}

/// Runs a toolchain against a test file and executable.
pub struct ToolChainRunner {
    pub tc: ToolChain,
    pub timeout: f64,
    /// Extra environment variables to inject into spawned subprocesses (e.g. runtime lib paths).
    pub extra_env: HashMap<String, String>,
    reserved_exit_codes: Vec<i32>,
    runtime_errors: Vec<&'static str>,
}

impl ToolChainRunner {
    pub fn new(tc: ToolChain, timeout: f64) -> Self {
        Self {
            tc,
            timeout,
            extra_env: HashMap::new(),
            reserved_exit_codes: vec![VALGRIND_EXIT_CODE],
            runtime_errors: vec!["SizeError", "IndexError", "MathError", "StrideError"],
        }
    }

    pub fn with_env(mut self, env: HashMap<String, String>) -> Self {
        self.extra_env = env;
        self
    }

    /// Run each step of the toolchain for a given test and executable.
    pub fn run(&self, test: &Arc<TestFile>, exe: &Executable) -> TestResult {
        let mut input_file = test.path.clone();
        let expected = test.get_expected_out().to_vec();
        let mut tr = TestResult::new(Arc::clone(test));
        let tc_len = self.tc.len();

        for (index, step) in self.tc.iter().enumerate() {
            let last_step = index == tc_len - 1;
            let input_stream = if step.uses_ins {
                test.get_input_stream().to_vec()
            } else {
                Vec::new()
            };

            let output_file = self.resolve_output_file(step);
            let magic = MagicParams {
                exe_path: exe.exe_path.clone(),
                input_file: input_file.clone(),
                output_file: output_file.clone(),
            };

            let command = self.resolve_command(step, &magic);
            let cr = self.run_command(&command, &input_stream);

            // Check timeout
            if cr.timed_out {
                tr.did_pass = false;
                tr.did_timeout = true;
                tr.failing_step = Some(step.name.clone());
                tr.time = Some(self.timeout);
                tr.command_history.push(cr);
                return tr;
            }

            // Check if OS failed to exec
            if cr.exit_status == -1 {
                tr.did_pass = false;
                tr.command_history.push(cr);
                return tr;
            }

            let stdout = cr.stdout.clone();
            let stderr = cr.stderr.clone();
            let step_time = (cr.time * 10000.0).round() / 10000.0;

            // Check reserved exit codes (e.g., valgrind)
            if self.reserved_exit_codes.contains(&cr.exit_status) {
                if cr.exit_status == VALGRIND_EXIT_CODE {
                    tr.memory_leak = true;
                }
            }

            if cr.exit_status != 0
                && !self.reserved_exit_codes.contains(&cr.exit_status)
            {
                tr.gen_output = Some(stderr.clone());
                tr.failing_step = Some(step.name.clone());
                tr.error_test = true;

                if step.allow_error {
                    self.handle_error_test(&mut tr, &stderr, &expected);
                    tr.command_history.push(cr);
                    return tr;
                } else {
                    tr.did_pass = false;
                    tr.command_history.push(cr);
                    return tr;
                }
            } else if last_step {
                let final_stdout = if let Some(ref out_path) = output_file {
                    if !Path::new(out_path).exists() {
                        tr.command_history.push(cr);
                        tr.did_pass = false;
                        return tr;
                    }
                    file_to_bytes(out_path).unwrap_or_default()
                } else {
                    stdout
                };

                tr.time = Some(step_time);
                tr.gen_output = Some(final_stdout.clone());
                tr.did_pass = precise_diff(&final_stdout, &expected).is_empty();
                tr.command_history.push(cr);
                return tr;
            } else {
                // Set up next step's input
                input_file = output_file.unwrap_or_else(|| {
                    make_tmp_file(&stdout).unwrap_or_default()
                });
                tr.command_history.push(cr);
            }
        }

        // Unreachable for well-defined toolchains
        panic!("Toolchain reached undefined conditions during execution.");
    }

    fn run_command(&self, command: &Command, stdin: &[u8]) -> CommandResult {
        let mut cr = CommandResult::new(&command.cmd);
        let start = Instant::now();

        let mut cmd = process::Command::new(&command.args[0]);
        cmd.args(&command.args[1..])
            .stdin(process::Stdio::piped())
            .stdout(process::Stdio::piped())
            .stderr(process::Stdio::piped())
            .envs(&self.extra_env);
        let result = cmd.spawn();

        match result {
            Ok(mut child) => {
                // Write stdin then close it
                if let Some(mut child_stdin) = child.stdin.take() {
                    use std::io::Write;
                    let _ = child_stdin.write_all(stdin);
                }

                let timeout_dur = Duration::from_secs_f64(self.timeout);
                match child.wait_timeout(timeout_dur) {
                    Ok(Some(status)) => {
                        // Process exited within timeout — read remaining output
                        cr.time = start.elapsed().as_secs_f64();
                        cr.exit_status = status.code().unwrap_or(1);

                        // Read stdout and stderr from the pipes
                        use std::io::Read;
                        if let Some(mut out) = child.stdout.take() {
                            let _ = out.read_to_end(&mut cr.stdout);
                        }
                        if let Some(mut err) = child.stderr.take() {
                            let _ = err.read_to_end(&mut cr.stderr);
                        }
                    }
                    Ok(None) => {
                        // Still running — timeout
                        let _ = child.kill();
                        let _ = child.wait();
                        cr.timed_out = true;
                        cr.time = self.timeout;
                        cr.exit_status = 255;
                    }
                    Err(_) => {
                        cr.exit_status = 1;
                        cr.time = start.elapsed().as_secs_f64();
                    }
                }
            }
            Err(_) => {
                cr.exit_status = -1;
                cr.time = start.elapsed().as_secs_f64();
            }
        }

        cr
    }

    fn resolve_output_file(&self, step: &Step) -> Option<String> {
        step.output.as_ref().map(|output| {
            let cwd = env::current_dir()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned();
            if Path::new(output).is_absolute() {
                output.clone()
            } else {
                Path::new(&cwd).join(output).to_string_lossy().into_owned()
            }
        })
    }

    fn resolve_command(&self, step: &Step, params: &MagicParams) -> Command {
        let mut args = vec![step.exe_path.clone()];
        args.extend(step.arguments.iter().cloned());
        let mut command = Command::new(args);
        self.replace_magic_args(&mut command, params);
        self.replace_env_vars(&mut command);
        // Make exe path absolute if relative
        if !command.args.is_empty() && !Path::new(&command.args[0]).is_absolute() {
            if let Ok(abs) = fs::canonicalize(&command.args[0]) {
                command.args[0] = abs.to_string_lossy().into_owned();
            } else if let Ok(cwd) = env::current_dir() {
                let abs = cwd.join(&command.args[0]);
                command.args[0] = abs.to_string_lossy().into_owned();
            }
        }
        command.cmd = command.args[0].clone();
        command
    }

    fn replace_magic_args(&self, command: &mut Command, params: &MagicParams) {
        for arg in command.args.iter_mut() {
            if arg.contains("$EXE") {
                *arg = arg.replace("$EXE", &params.exe_path);
            } else if arg.contains("$INPUT") && !params.input_file.is_empty() {
                *arg = arg.replace("$INPUT", &params.input_file);
            } else if arg.contains("$OUTPUT") {
                if let Some(ref out) = params.output_file {
                    *arg = arg.replace("$OUTPUT", out);
                }
            }
        }
        if let Some(first) = command.args.first() {
            command.cmd = first.clone();
        }
    }

    fn replace_env_vars(&self, command: &mut Command) {
        for arg in command.args.iter_mut() {
            let original = arg.clone();
            for caps in ENV_VAR_RE.captures_iter(&original) {
                let var_name = caps
                    .get(1)
                    .or_else(|| caps.get(2))
                    .map(|m| m.as_str())
                    .unwrap_or("");
                // Check runner's extra_env first, then fall back to process env
                let val = self.extra_env.get(var_name).cloned()
                    .or_else(|| env::var(var_name).ok());
                if let Some(val) = val {
                    *arg = arg
                        .replace(&format!("${var_name}"), &val)
                        .replace(&format!("${{{var_name}}}"), &val);
                }
            }
        }
    }

    fn handle_error_test(&self, tr: &mut TestResult, produced: &[u8], expected: &[u8]) {
        let produced_str = match std::str::from_utf8(produced) {
            Ok(s) => s.trim().to_string(),
            Err(_) => {
                tr.did_pass = false;
                return;
            }
        };
        let expected_str = match std::str::from_utf8(expected) {
            Ok(s) => s.trim().to_string(),
            Err(_) => {
                tr.did_pass = false;
                return;
            }
        };

        if produced_str.is_empty() || expected_str.is_empty() {
            tr.did_pass = false;
            return;
        }

        let rt_error = self
            .runtime_errors
            .iter()
            .find(|e| expected_str.contains(**e))
            .copied();
        let did_raise_rt = self
            .runtime_errors
            .iter()
            .any(|e| produced_str.contains(e));

        if did_raise_rt {
            if let Some(rt_err) = rt_error {
                let pattern = format!(r"{}(\s+on\s+Line\s+\d+)?(:.+)?", rt_err);
                let re = Regex::new(&pattern).unwrap();
                tr.did_pass = re.is_match(&produced_str) && re.is_match(&expected_str);
            } else {
                tr.did_pass = false;
            }
        } else {
            let prod_error = ERROR_KIND_RE.captures(&produced_str);
            let exp_error = ERROR_KIND_RE.captures(&expected_str);
            let prod_line = ERROR_LINE_RE.captures(&produced_str);
            let exp_line = ERROR_LINE_RE.captures(&expected_str);

            // MainError hack
            if let (Some(ref pe), Some(ref ee)) = (&prod_error, &exp_error) {
                if pe.get(1).map(|m| m.as_str()) == Some("MainError")
                    && ee.get(1).map(|m| m.as_str()) == Some("MainError")
                {
                    tr.did_pass = true;
                    return;
                }
            }

            if prod_error.is_some() && exp_error.is_some() && prod_line.is_some() && exp_line.is_some()
            {
                tr.did_pass = prod_line.unwrap().get(1).map(|m| m.as_str())
                    == exp_line.unwrap().get(1).map(|m| m.as_str());
            } else {
                tr.did_pass = false;
            }
        }
    }
}

/// Byte-level diff between two byte slices.
pub fn diff_bytes(s1: &[u8], s2: &[u8]) -> String {
    let mut result = String::new();
    let mut i = 0;
    let mut j = 0;
    while i < s1.len() && j < s2.len() {
        if s1[i] != s2[j] {
            result.push_str(&format!("-{}", s1[i]));
            result.push_str(&format!("+{}", s2[j]));
        } else {
            result.push_str(&format!(" {}", s1[i]));
        }
        i += 1;
        j += 1;
    }
    while i < s1.len() {
        result.push_str(&format!("-{}", s1[i]));
        i += 1;
    }
    while j < s2.len() {
        result.push_str(&format!("+{}", s2[j]));
        j += 1;
    }
    result
}

/// Return a diff string if produced != expected, empty string if equal.
pub fn precise_diff(produced: &[u8], expected: &[u8]) -> String {
    if produced == expected {
        String::new()
    } else {
        diff_bytes(produced, expected)
    }
}

#[cfg(test)]
mod tests {
    use std::path::PathBuf;

    use crate::config::{load_config, Config};
    use super::ToolChainRunner;

    fn configs_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests").join("configs")
    }

    fn config_path(name: &str) -> String {
        configs_dir().join(name).to_string_lossy().into_owned()
    }

    fn create_config(name: &str) -> Config {
        let path = config_path(name);
        load_config(&path, None).expect("config should load")
    }

    fn run_tests_for_config(config: &Config, expected_result: bool) {
        for exe in &config.executables {
            for tc in &config.toolchains {
                let runner = ToolChainRunner::new(tc.clone(), 10.0)
                    .with_env(exe.runtime_env());
                for pkg in &config.packages {
                    for spkg in &pkg.subpackages {
                        for test in &spkg.tests {
                            let result = runner.run(test, exe);
                            assert_eq!(
                                result.did_pass, expected_result,
                                "Test {} expected {} but got {}",
                                test.file,
                                if expected_result { "PASS" } else { "FAIL" },
                                if result.did_pass { "PASS" } else { "FAIL" },
                            );
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn test_gcc_pass() {
        let config = create_config("gccPassConfig.json");
        assert!(config.errors.is_empty(), "config errors: {:?}", config.errors);
        run_tests_for_config(&config, true);
    }

    #[test]
    fn test_gcc_fail() {
        let config = create_config("gccFailConfig.json");
        assert!(config.errors.is_empty(), "config errors: {:?}", config.errors);
        run_tests_for_config(&config, false);
    }

    #[test]
    fn test_runtime_gcc_toolchain() {
        let tests_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests");
        let compile_script = tests_dir.join("scripts/test-scripts/compile_lib.py");
        let lib_src_dir = tests_dir.join("lib/src");
        let lib_out_dir = tests_dir.join("lib");

        assert!(compile_script.exists(), "missing compile_lib.py");

        let expected_lib = tests_dir.join("lib/libfib.so");
        if !expected_lib.exists() {
            let status = std::process::Command::new("python3")
                .args([
                    compile_script.to_str().unwrap(),
                    lib_src_dir.to_str().unwrap(),
                    lib_out_dir.to_str().unwrap(),
                ])
                .status()
                .expect("failed to run compile_lib.py");
            assert!(status.success(), "shared object compilation failed");
            assert!(expected_lib.exists(), "failed to create shared object");
        }

        let path = config_path("runtimeConfigLinux.json");
        let config = load_config(&path, None).expect("config should load");
        assert!(config.errors.is_empty(), "config errors: {:?}", config.errors);
        run_tests_for_config(&config, true);
    }
}
