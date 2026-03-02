use std::collections::HashMap;
use std::env;
use std::fs;
use std::ops::ControlFlow;
use std::path::{Path, PathBuf};
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
use crate::util::{make_tmp_file, make_empty_tmp_file};

/// Reserved exit code for valgrind leak detection.
pub const VALGRIND_EXIT_CODE: i32 = 111;

const RESERVED_EXIT_CODES: &[i32] = &[VALGRIND_EXIT_CODE];
const RUNTIME_ERRORS: &[&str] = &["SizeError", "IndexError", "MathError", "StrideError"];

/// State threaded between pipeline steps during a toolchain run.
struct PipelineState {
    input_file: PathBuf,
    tmp_handles: Vec<tempfile::TempPath>,
    command_history: Vec<CommandResult>,
    memory_leak: bool,
}

/// Magic variable placeholders used in toolchain step arguments.
pub enum MagicArg {
    Exe,
    Input,
    Output,
}

impl MagicArg {
    pub const ALL: &[MagicArg] = &[MagicArg::Exe, MagicArg::Input, MagicArg::Output];

    pub fn pattern(&self) -> &'static str {
        match self {
            MagicArg::Exe => "$EXE",
            MagicArg::Input => "$INPUT",
            MagicArg::Output => "$OUTPUT",
        }
    }

    fn resolve<'a>(&self, params: &'a MagicParams) -> Option<&'a str> {
        match self {
            MagicArg::Exe => Some(&params.exe_path),
            MagicArg::Input if !params.input_file.is_empty() => Some(&params.input_file),
            MagicArg::Input => None,
            MagicArg::Output => params.output_file.as_deref(),
        }
    }
}

/// Magic parameter values substituted into toolchain step arguments.
pub struct MagicParams {
    pub exe_path: String,
    pub input_file: String,
    pub output_file: Option<String>,
}

/// A resolved command ready to execute.
pub struct ResolvedCommand {
    pub args: Vec<String>,
}

impl ResolvedCommand {
    pub fn new(args: Vec<String>) -> Self {
        Self { args }
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
    fn finished(
        test: &Arc<TestFile>,
        history: Vec<CommandResult>,
        output: Vec<u8>,
        time: f64,
        memory_leak: bool,
    ) -> Self {
        let expected = test.get_expected_out();
        Self {
            did_pass: output == expected,
            test: Arc::clone(test),
            did_timeout: false,
            error_test: false,
            memory_leak,
            command_history: history,
            gen_output: Some(output),
            time: Some(time),
            failing_step: None,
        }
    }

    fn timeout(
        test: &Arc<TestFile>,
        history: Vec<CommandResult>,
        step_name: &str,
        timeout: f64,
    ) -> Self {
        Self {
            test: Arc::clone(test),
            did_pass: false,
            did_timeout: true,
            error_test: false,
            memory_leak: false,
            command_history: history,
            gen_output: None,
            time: Some(timeout),
            failing_step: Some(step_name.to_string()),
        }
    }

    fn fail(test: &Arc<TestFile>, history: Vec<CommandResult>, failing_step: Option<String>) -> Self {
        Self {
            test: Arc::clone(test),
            did_pass: false,
            did_timeout: false,
            error_test: false,
            memory_leak: false,
            command_history: history,
            gen_output: None,
            time: None,
            failing_step,
        }
    }

    fn error(
        test: &Arc<TestFile>,
        history: Vec<CommandResult>,
        stderr: Vec<u8>,
        step_name: &str,
        did_pass: bool,
        memory_leak: bool,
    ) -> Self {
        Self {
            test: Arc::clone(test),
            did_pass,
            did_timeout: false,
            error_test: true,
            memory_leak,
            command_history: history,
            gen_output: Some(stderr),
            time: None,
            failing_step: Some(step_name.to_string()),
        }
    }
}

const VALGRIND_BIN: &str = "valgrind";

/// Runs a toolchain against a test file and executable.
pub struct ToolChainRunner<'a> {
    pub tc: &'a ToolChain,
    pub timeout: f64,
    /// Extra environment variables to inject into spawned subprocesses (e.g. runtime lib paths).
    pub extra_env: HashMap<String, String>,
    /// When true, automatically wrap the last toolchain step with valgrind.
    pub memcheck: bool,
}

impl<'a> ToolChainRunner<'a> {
    pub fn new(tc: &'a ToolChain, timeout: f64) -> Self {
        Self {
            tc,
            timeout,
            extra_env: HashMap::new(),
            memcheck: false,
        }
    }

    pub fn with_env(mut self, env: HashMap<String, String>) -> Self {
        self.extra_env = env;
        self
    }

    pub fn with_memcheck(mut self, memcheck: bool) -> Self {
        self.memcheck = memcheck;
        self
    }

    /// Run each step of the toolchain for a given test and executable.
    pub fn run(&self, test: &Arc<TestFile>, exe: &Executable) -> TestResult {
        let tc_len = self.tc.len();
        let init = PipelineState {
            input_file: test.path.clone(),
            tmp_handles: Vec::new(),
            command_history: Vec::new(),
            memory_leak: false,
        };

        let result = self.tc.iter().enumerate().try_fold(init, |state, (index, step)| {
            self.run_step(state, step, index == tc_len - 1, test, exe)
        });

        match result {
            ControlFlow::Break(tr) => tr,
            ControlFlow::Continue(_) => panic!("Toolchain reached undefined conditions"),
        }
    }

    fn run_step(
        &self,
        mut state: PipelineState,
        step: &Step,
        last_step: bool,
        test: &Arc<TestFile>,
        exe: &Executable,
    ) -> ControlFlow<TestResult, PipelineState> {
        
        let input_stream = if step.uses_ins { test.get_input_stream() } else { b"" };
        let output_resolved = self.resolve_output_file(step);
        let output_path = output_resolved.as_ref().map(|(p, _)| p.clone());
        let magic = MagicParams {
            exe_path: exe.exe_path.display().to_string(),
            input_file: state.input_file.display().to_string(),
            output_file: output_path.as_ref().map(|p| p.display().to_string()),
        };

        // Keep temp handle alive for the duration of the step
        if let Some((_, handle)) = output_resolved {
            state.tmp_handles.push(handle);
        }

        let mut command = self.resolve_command(step, &magic);

        // In memcheck mode, wrap the last step with valgrind
        if self.memcheck && last_step && !self.wrap_valgrind(&mut command) {
            return ControlFlow::Break(TestResult::fail(
                test, state.command_history,
                Some("memcheck: valgrind not found".to_string()),
            ));
        }

        let cr = self.run_command(&command, &input_stream);
        if cr.timed_out {
            state.command_history.push(cr);
            return ControlFlow::Break(TestResult::timeout(
                test, state.command_history, &step.display_name(exe), self.timeout,
            ));
        }

        if cr.exit_status == -1 {
            state.command_history.push(cr);
            return ControlFlow::Break(TestResult::fail(
                test, state.command_history, None,
            ));
        }

        let stdout = cr.stdout.clone();
        let stderr = cr.stderr.clone();
        let step_time = (cr.time * 10000.0).round() / 10000.0;
        let exit_status = cr.exit_status;

        if exit_status == VALGRIND_EXIT_CODE {
            state.memory_leak = true;
        }
        state.command_history.push(cr);

        if exit_status != 0 && !RESERVED_EXIT_CODES.contains(&exit_status) {
            let did_pass = step.allow_error
                && self.check_error_test(&stderr, test.get_expected_out());
            return ControlFlow::Break(TestResult::error(
                test, state.command_history, stderr,
                &step.display_name(exe), did_pass, state.memory_leak,
            ));
        }

        if last_step {
            let final_output = match output_path {
                Some(ref p) if p.exists() => fs::read(p).unwrap_or_default(),
                Some(_) => return ControlFlow::Break(TestResult::finished(
                    test, state.command_history, Vec::new(), step_time, state.memory_leak,
                )),
                None => stdout,
            };
            return ControlFlow::Break(TestResult::finished(
                test, state.command_history, final_output, step_time, state.memory_leak,
            ));
        }

        // Not the last step — continue the pipeline
        state.input_file = output_path.unwrap_or_else(|| {
            match make_tmp_file(&stdout) {
                Some((path, handle)) => {
                    state.tmp_handles.push(handle);
                    path
                }
                None => PathBuf::new(),
            }
        });
        ControlFlow::Continue(state)
    }

    /// Prepend valgrind flags to command. Returns false if valgrind is not installed.
    fn wrap_valgrind(&self, command: &mut ResolvedCommand) -> bool {
        let ok = process::Command::new(VALGRIND_BIN)
            .arg("--version")
            .stdout(process::Stdio::null())
            .stderr(process::Stdio::null())
            .status()
            .is_ok_and(|s| s.success());
        if ok {
            let mut wrapped = vec![
                VALGRIND_BIN.to_string(),
                "--leak-check=full".to_string(),
                format!("--error-exitcode={VALGRIND_EXIT_CODE}"),
                "--log-file=/dev/null".to_string(),
            ];
            wrapped.append(&mut command.args);
            command.args = wrapped;
        }
        ok
    }

    fn run_command(&self, command: &ResolvedCommand, stdin: &[u8]) -> CommandResult {
        let mut cr = CommandResult::new(&command.args[0]);
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

    fn resolve_output_file(&self, step: &Step) -> Option<(PathBuf, tempfile::TempPath)> {
        if step.args.iter().any(|a| a.contains(MagicArg::Output.pattern())) {
            make_empty_tmp_file()
        } else {
            None
        }
    }

    fn resolve_command(&self, step: &Step, params: &MagicParams) -> ResolvedCommand {
        let mut args = vec![step.exe_raw.clone()];
        args.extend(step.args.iter().cloned());
        let mut command = ResolvedCommand::new(args);
        self.replace_magic_args(&mut command, params);
        self.replace_env_vars(&mut command);
        // Only resolve paths containing '/' — bare names (e.g. "gcc") use $PATH lookup
        if !command.args.is_empty() && command.args[0].contains('/') && !Path::new(&command.args[0]).is_absolute() {
            if let Ok(abs) = fs::canonicalize(&command.args[0]) {
                command.args[0] = abs.to_string_lossy().into_owned();
            } else if let Ok(cwd) = env::current_dir() {
                let abs = cwd.join(&command.args[0]);
                command.args[0] = abs.to_string_lossy().into_owned();
            }
        }
        command
    }

    fn replace_magic_args(&self, command: &mut ResolvedCommand, params: &MagicParams) {
        for arg in command.args.iter_mut() {
            for magic in MagicArg::ALL {
                if arg.contains(magic.pattern()) {
                    if let Some(val) = magic.resolve(params) {
                        *arg = arg.replace(magic.pattern(), val);
                    }
                }
            }
        }
    }

    fn replace_env_vars(&self, command: &mut ResolvedCommand) {
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

    fn check_error_test(&self, produced: &[u8], expected: &[u8]) -> bool {
        let produced_str = match std::str::from_utf8(produced) {
            Ok(s) => s.trim(),
            Err(_) => return false,
        };
        let expected_str = match std::str::from_utf8(expected) {
            Ok(s) => s.trim(),
            Err(_) => return false,
        };

        if produced_str.is_empty() || expected_str.is_empty() {
            return false;
        }

        let rt_error = RUNTIME_ERRORS
            .iter()
            .find(|e| expected_str.contains(**e))
            .copied();
        let did_raise_rt = RUNTIME_ERRORS
            .iter()
            .any(|e| produced_str.contains(e));

        if did_raise_rt {
            if let Some(rt_err) = rt_error {
                let pattern = format!(r"{}(\s+on\s+Line\s+\d+)?(:.+)?", rt_err);
                let re = Regex::new(&pattern).unwrap();
                re.is_match(produced_str) && re.is_match(expected_str)
            } else {
                false
            }
        } else {
            let prod_error = ERROR_KIND_RE.captures(produced_str);
            let exp_error = ERROR_KIND_RE.captures(expected_str);
            let prod_line = ERROR_LINE_RE.captures(produced_str);
            let exp_line = ERROR_LINE_RE.captures(expected_str);
            match (prod_error, exp_error, prod_line, exp_line) {
                (Some(_), Some(_), Some(pl), Some(el)) => {
                    pl.get(1).map(|m| m.as_str()) == el.get(1).map(|m| m.as_str())
                }
                _ => false,
            }
        }
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

    fn config_path(name: &str) -> PathBuf {
        configs_dir().join(name)
    }

    fn create_config(name: &str) -> Config {
        let path = config_path(name);
        load_config(&path, None).expect("config should load")
    }

    fn _assert_send_sync() {
        fn check<T: Send + Sync>() {}
        check::<ToolChainRunner<'_>>();
    }

    fn run_tests_for_config(config: &Config, expected_result: bool) {
        for exe in &config.executables {
            for tc in &config.toolchains {
                let runner = ToolChainRunner::new(tc, 10.0)
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

    fn valgrind_available() -> bool {
        std::process::Command::new("valgrind")
            .arg("--version")
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .is_ok_and(|s: std::process::ExitStatus| s.success())
    }

    /// Memcheck wrapping works on gccPassConfig — runner still produces results.
    #[test]
    fn test_memcheck_clean_programs() {
        if !valgrind_available() {
            eprintln!("skipping: valgrind not found");
            return;
        }
        let config = create_config("gccPassConfig.json");
        assert!(config.errors.is_empty(), "config errors: {:?}", config.errors);
        let mut ran_any = false;
        for exe in &config.executables {
            for tc in &config.toolchains {
                let runner = ToolChainRunner::new(tc, 10.0)
                    .with_env(exe.runtime_env())
                    .with_memcheck(true);
                for pkg in &config.packages {
                    for spkg in &pkg.subpackages {
                        for test in &spkg.tests {
                            let result = runner.run(test, exe);
                            ran_any = true;
                            // Tests that don't leak should still pass and not flag a leak
                            if !test.file.contains("memleak") {
                                assert!(
                                    !result.memory_leak,
                                    "Non-leaky test {} should not flag memory leak",
                                    test.file,
                                );
                            }
                        }
                    }
                }
            }
        }
        assert!(ran_any, "should have run at least one test");
    }

    /// Memcheck on MemoryLeaks package — leaky programs should be flagged.
    #[test]
    fn test_memcheck_detects_leaks() {
        if !valgrind_available() {
            eprintln!("skipping: valgrind not found");
            return;
        }
        let config = create_config("gccMemcheckConfig.json");
        assert!(config.errors.is_empty(), "config errors: {:?}", config.errors);
        for exe in &config.executables {
            for tc in &config.toolchains {
                let runner = ToolChainRunner::new(tc, 10.0)
                    .with_env(exe.runtime_env())
                    .with_memcheck(true);
                for pkg in &config.packages {
                    for spkg in &pkg.subpackages {
                        for test in &spkg.tests {
                            let result = runner.run(test, exe);
                            if test.path.to_string_lossy().contains("leaky") {
                                assert!(
                                    result.memory_leak,
                                    "Leaky test {} should be detected as memory leak",
                                    test.file,
                                );
                            } else if test.path.to_string_lossy().contains("safe") && test.file.contains("001_safe") {
                                assert!(
                                    !result.memory_leak,
                                    "Safe test {} should not have memory leak",
                                    test.file,
                                );
                            }
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn test_runtime_gcc_toolchain() {
        let tests_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests");
        let compile_script = tests_dir.join("scripts/test-scripts/compile_lib.py");
        let lib_src_dir = tests_dir.join("lib/src");
        let lib_out_dir = tests_dir.join("lib");

        assert!(compile_script.exists(), "missing compile_lib.py");

        let (lib_name, config_name) = if cfg!(target_os = "macos") {
            ("lib/libfib.dylib", "runtimeConfigDarwin.json")
        } else {
            ("lib/libfib.so", "runtimeConfigLinux.json")
        };
        let expected_lib = tests_dir.join(lib_name);
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

        let path = config_path(config_name);
        let config = load_config(&path, None).expect("config should load");
        assert!(config.errors.is_empty(), "config errors: {:?}", config.errors);
        run_tests_for_config(&config, true);
    }
}
