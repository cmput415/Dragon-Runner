# Dragon-Runner

A test runner for CMPUT 415 Compiler Design that services both student testing and automated grading.

## Installation

**Requirements:** Rust toolchain (cargo)

```bash
git clone https://github.com/cmput415/Dragon-Runner.git
cd Dragon-Runner
cargo install --path .
```

## Quick Start

```bash
# Run tests normally (mode defaults to regular)
dragon-runner config.json

# Run in tournament mode (for grading)
dragon-runner tournament config.json

# Check for memory leaks (see Valgrind Config in `/tests`)
dragon-runner memcheck valgrindConfig.json

# Start HTTP server for explorer
dragon-runner serve /path/to/config.json
```

## Configuration

Dragon-Runner uses JSON configuration files to define test packages, executables, and toolchains.

### Basic Example

```json
{
  "testDir": "../packages/CPackage",
  "testedExecutablePaths": {
    "gcc": "/usr/bin/gcc"
  },
  "toolchains": {
    "compile-and-run": [
      {
        "exe": "$EXE",
        "args": ["$INPUT", "-o", "$OUTPUT"],
        "allowError": true
      },
      {
        "exe": "$INPUT",
        "usesInStr": true,
        "allowError": true
      }
    ]
  }
}
```

### Configuration Reference

#### Top-level Properties
| Property | Description | Required |
|----------|-------------|----------|
| `testDir` | Path to directory containing test packages | ✓ |
| `testedExecutablePaths` | Map of executable IDs to file paths | ✓ |
| `toolchains` | Map of toolchain names to step lists | ✓ |
| `runtimes` | Map of runtime libraries (optional) | |
| `solutionExecutable` | Reference solution ID (optional) | |

#### Toolchain Steps
| Property | Description | Required |
|----------|-------------|----------|
| `exe` | Path to executable (supports `$EXE`, `$INPUT`, `$OUTPUT`) | ✓ |
| `args` | Command arguments list (default: `[]`) | |
| `allowError` | Allow non-zero exit codes (default: `false`) | |
| `usesInStr` | Use test input stream as stdin (default: `false`) | |
| `usesRuntime` | Load runtime library (default: `false`) | |

#### Magic Variables
- `$EXE` — Path to the tested executable
- `$INPUT` — Input file (test file for first step, previous output for later steps)
- `$OUTPUT` — Temporary output file for the next step

Environment variables (`$RT_PATH`, `$RT_LIB`, etc.) are also expanded in step arguments.

## Test File Format

Tests support inline directives using comment syntax:

```c
// INPUT: hello world
// CHECK: HELLO WORLD

int main() {
    // Your test code here
    return 0;
}
```

### Directives
- `CHECK:` — Expected stdout line (no trailing newline)
- `CHECK_FILE:` — Path to expected output file
- `INPUT:` — Single line of stdin (no trailing newline)
- `INPUT_FILE:` — Path to input file
- `SKIP` — Skip this test

Multiple `CHECK:` and `INPUT:` directives are concatenated with newlines. Inline and file variants of the same directive cannot be mixed in one test.

## Command Line Reference

### Basic Usage
```bash
dragon-runner [mode] config.json [options...]
```

If no mode subcommand is given, `regular` is assumed.

### Modes
- `regular` (default) — Standard test execution
- `tournament` — Cross-product testing for grading
- `perf` — Performance benchmarking
- `memcheck` — Memory leak detection via valgrind
- `serve` — HTTP server mode
- `script` — Run grading scripts

### Options
| Option | Description |
|--------|-------------|
| `--timeout SECONDS` | Test timeout (default: 2.0) |
| `--fail-log FILE` | Log failures to file |
| `--verify` | Verify package exists for CCID |
| `--debug-package PATH` | Test single package |
| `-p, --package PATTERN` | Filter packages by glob pattern |
| `-t, --time` | Show execution times |
| `-v, --verbosity` | Increase output verbosity (repeat for more) |
| `-s, --show-testcase` | Display test file contents on failure |
| `-o, --output FILE` | Output file for results |
| `-f, --fast-fail` | Stop on first failure |
| `--full-path` | Print full file paths for test results |

### Examples

```bash
# Basic testing with timing
dragon-runner -t config.json

# Verbose tournament mode
dragon-runner tournament -vv config.json

# Performance testing with 5-second timeout
dragon-runner perf --timeout 5.0 config.json

# Serve config on custom address
dragon-runner serve --bind 0.0.0.0:8080 config.json

# Run grading script
dragon-runner script build.py /path/to/submissions build.log 4
```

## Contributing

Contributions welcome! Please file issues for bugs or feature requests, and feel free to submit pull requests.
