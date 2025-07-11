# Dragon-Runner

A test runner for CMPUT 415 Compiler Design that services both student testing and automated grading.

## Installation

**Requirements:** Python ≥ 3.8

```bash
git clone https://github.com/cmput415/Dragon-Runner.git
cd Dragon-Runner
pip install .
```
Some newer versions of python prevent system-wide package installations by default. To get around this use a virtual environment or `--break-system-packages`. If `dragon-runner`is not found in your `$PATH` after install, ensure `~/.local/bin` is added.

## Quick Start

```bash
# Run tests normally
dragon-runner config.json

# Run in tournament mode (for grading)
dragon-runner tournament config.json

# Check for memory leaks (see Valgrind Config in `/tests`)
dragon-runner memcheck valgrindConfig.json

# Start HTTP server for explorer
dragon-runner serve /path/to/configs
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
        "stepName": "compile",
        "executablePath": "$EXE", 
        "arguments": ["$INPUT", "-o", "$OUTPUT"],
        "output": "/tmp/test.o",
        "allowError": true
      },
      {
        "stepName": "run",
        "executablePath": "$INPUT",
        "arguments": [],
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
| `stepName` | Human-readable step name | ✓ |
| `executablePath` | Path to executable (use `$EXE`, `$INPUT`) | ✓ |
| `arguments` | Command arguments list | ✓ |
| `output` | Output file path (optional) | |
| `allowError` | Allow non-zero exit codes (optional) | |
| `usesInStr` | Use test input stream as stdin (optional) | |
| `usesRuntime` | Load runtime library (optional) | |

#### Magic Variables
- `$EXE` - Path to the tested executable
- `$INPUT` - Input file (testfile for first step, previous output for others)
- `$OUTPUT` - Output file for next step
- `$RT_PATH` - Runtime library directory
- `$RT_LIB` - Runtime library name

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
- `INPUT:` - Single line of stdin (no newline)
- `INPUT_FILE:` - Path to input file
- `CHECK:` - Expected stdout (no newline)  
- `CHECK_FILE:` - Path to expected output file

Multiple `INPUT:` and `CHECK:` directives are supported. `INPUT:` and `INPUT_FILE:` cannot be used together.

## Command Line Reference

### Basic Usage
```bash
dragon-runner [mode] config.json [options...]
```

### Modes
- `regular` (default) - Standard test execution
- `tournament` - Cross-product testing for grading
- `perf` - Performance benchmarking
- `memcheck` - Memory leak detection
- `serve` - HTTP server mode
- `script` - Run grading scripts

### Options
| Option | Description |
|--------|-------------|
| `--timeout SECONDS` | Test timeout (default: 2.0) |
| `--fail-log FILE` | Log failures to file |
| `--verify` | Verify package exists for CCID |
| `--debug-package PATH` | Test single package |
| `-t, --time` | Show execution times |
| `-v, --verbosity` | Increase output verbosity (repeat for more) |
| `-s, --show-testcase` | Display test file contents |
| `-o, --output FILE` | Output file for results |

### Examples

```bash
# Basic testing with timing
dragon-runner -t config.json

# Verbose tournament mode
dragon-runner tournament -vv config.json

# Performance testing with 5-second timeout
dragon-runner perf --timeout 5.0 config.json

# Serve configs on port 8080
dragon-runner serve --port 8080 /path/to/configs

# Run grading script
dragon-runner script build.py /path/to/submissions build.log 4
```

## Contributing

Contributions welcome! Please file issues for bugs or feature requests, and feel free to submit pull requests.
