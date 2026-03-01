use std::sync::Arc;

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine;
use serde::{Deserialize, Serialize};
use tokio::sync::Semaphore;
use tower_http::cors::CorsLayer;

use crate::config::{Config, Executable};
use crate::runner::ToolChainRunner;
use crate::testfile::TestFile;
use crate::toolchain::ToolChain;

struct AppState {
    config: Config,
    timeout: f64,
    run_semaphore: Semaphore,
}

// ---------------------------------------------------------------------------
// Request / Response types
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct RunRequest {
    toolchain: String,
    executable: String,
    code: String,
    stdin: Option<String>,
    expected_output: Option<String>,
}

#[derive(Serialize)]
struct RunResponse {
    passed: bool,
    exit_status: i32,
    stdout: String,
    stderr: String,
    time_secs: Option<f64>,
    timed_out: bool,
    error_test: bool,
    failing_step: Option<String>,
    steps: Vec<StepInfo>,
}

#[derive(Serialize)]
struct StepInfo {
    name: String,
    exit_status: i32,
    time_secs: f64,
}

#[derive(Serialize)]
struct InfoResponse {
    config_name: String,
    toolchains: Vec<ToolchainInfo>,
    executables: Vec<ExecutableInfo>,
    packages: Vec<PackageInfo>,
}

#[derive(Serialize)]
struct ToolchainInfo {
    name: String,
    num_steps: usize,
}

#[derive(Serialize)]
struct ExecutableInfo {
    id: String,
    path: String,
}

#[derive(Serialize)]
struct PackageInfo {
    name: String,
    num_tests: usize,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

fn error_json(status: StatusCode, msg: impl Into<String>) -> (StatusCode, Json<ErrorResponse>) {
    (status, Json(ErrorResponse { error: msg.into() }))
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async fn health() -> &'static str {
    "OK"
}

async fn info(State(state): State<Arc<AppState>>) -> Json<InfoResponse> {
    let cfg = &state.config;
    Json(InfoResponse {
        config_name: cfg.name.clone(),
        toolchains: cfg
            .toolchains
            .iter()
            .map(|tc| ToolchainInfo {
                name: tc.name.clone(),
                num_steps: tc.len(),
            })
            .collect(),
        executables: cfg
            .executables
            .iter()
            .map(|e| ExecutableInfo {
                id: e.id.clone(),
                path: e.exe_path.display().to_string(),
            })
            .collect(),
        packages: cfg
            .packages
            .iter()
            .map(|p| PackageInfo {
                name: p.name.clone(),
                num_tests: p.n_tests,
            })
            .collect(),
    })
}

async fn run(
    State(state): State<Arc<AppState>>,
    Json(req): Json<RunRequest>,
) -> Result<Json<RunResponse>, (StatusCode, Json<ErrorResponse>)> {
    // Look up toolchain by name
    let tc: ToolChain = state
        .config
        .toolchains
        .iter()
        .find(|tc| tc.name == req.toolchain)
        .cloned()
        .ok_or_else(|| error_json(StatusCode::BAD_REQUEST, format!("unknown toolchain: {}", req.toolchain)))?;

    // Look up executable by id
    let exe: Executable = state
        .config
        .executables
        .iter()
        .find(|e| e.id == req.executable)
        .cloned()
        .ok_or_else(|| error_json(StatusCode::BAD_REQUEST, format!("unknown executable: {}", req.executable)))?;

    // Decode source code
    let code_bytes = B64.decode(&req.code)
        .map_err(|e| error_json(StatusCode::BAD_REQUEST, format!("invalid base64 in code: {e}")))?;

    // Decode optional stdin
    let stdin_bytes = req.stdin
        .as_ref()
        .map(|s| B64.decode(s))
        .transpose()
        .map_err(|e| error_json(StatusCode::BAD_REQUEST, format!("invalid base64 in stdin: {e}")))?;

    // Decode optional expected_output
    let expected_bytes = req.expected_output
        .as_ref()
        .map(|s| B64.decode(s))
        .transpose()
        .map_err(|e| error_json(StatusCode::BAD_REQUEST, format!("invalid base64 in expected_output: {e}")))?;

    // Acquire semaphore permit for backpressure
    let _permit = state.run_semaphore.acquire().await
        .map_err(|_| error_json(StatusCode::SERVICE_UNAVAILABLE, "server shutting down"))?;

    let timeout = state.timeout;

    // Run the toolchain in a blocking task
    let result = tokio::task::spawn_blocking(move || {
        // Write code to a temp file
        let tmp = tempfile::Builder::new()
            .suffix(".test")
            .tempfile()
            .map_err(|e| format!("failed to create temp file: {e}"))?;

        {
            use std::io::Write;
            let mut f = tmp.as_file();
            f.write_all(&code_bytes)
                .map_err(|e| format!("failed to write temp file: {e}"))?;
        }

        // Build TestFile from the temp path
        let mut test = TestFile::new(tmp.path());

        // Override directives if provided in the request
        if let Some(input) = stdin_bytes {
            test.input_stream = Ok(input);
        }
        if let Some(expected) = expected_bytes {
            test.expected_out = Ok(expected);
        }

        let test = Arc::new(test);

        let runner = ToolChainRunner::new(&tc, timeout)
            .with_env(exe.runtime_env());

        let result = runner.run(&test, &exe);
        Ok::<_, String>(result)
    })
    .await
    .map_err(|e| error_json(StatusCode::INTERNAL_SERVER_ERROR, format!("task panicked: {e}")))?
    .map_err(|e| error_json(StatusCode::INTERNAL_SERVER_ERROR, e))?;

    // Build step info from command history
    let steps: Vec<StepInfo> = result
        .command_history
        .iter()
        .map(|cr| StepInfo {
            name: cr.cmd.clone(),
            exit_status: cr.exit_status,
            time_secs: cr.time,
        })
        .collect();

    let last_exit = result
        .command_history
        .last()
        .map(|cr| cr.exit_status)
        .unwrap_or(0);

    let stdout_b64 = result
        .gen_output
        .as_deref()
        .map(|b| B64.encode(b))
        .unwrap_or_default();

    let stderr_b64 = result
        .command_history
        .last()
        .map(|cr| B64.encode(&cr.stderr))
        .unwrap_or_default();

    Ok(Json(RunResponse {
        passed: result.did_pass,
        exit_status: last_exit,
        stdout: stdout_b64,
        stderr: stderr_b64,
        time_secs: result.time,
        timed_out: result.did_timeout,
        error_test: result.error_test,
        failing_step: result.failing_step,
        steps,
    }))
}

// ---------------------------------------------------------------------------
// Server entrypoint
// ---------------------------------------------------------------------------

pub async fn run_server(config: Config, bind: &str, timeout: f64, max_concurrent: usize) {
    let state = Arc::new(AppState {
        config,
        timeout,
        run_semaphore: Semaphore::new(max_concurrent),
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/api/info", get(info))
        .route("/api/run", post(run))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(bind)
        .await
        .unwrap_or_else(|e| panic!("failed to bind to {bind}: {e}"));

    println!("dragon-runner server listening on {bind}");

    axum::serve(listener, app)
        .await
        .expect("server error");
}
