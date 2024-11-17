<div align="center">

# Dragon-Runner
#### A Custom Test Runner for CMPUT 415
<div style="background-color: #f0f0f0; border-radius: 10px; padding: 10px; display: inline-block;"> 
  <img alt="Dragon-Runner Logo" src="/docs/runner-log.png" width="90">
</div>
</div>
<br>


## What is Dragon-Runner

`dragon-runner` is a successor to the [415-tester](https://github.com/cmput415/Tester). Its name is derived by being a test runner for a compiler class that likes dragon iconography. `dragon-runner` has dual functions for students and graders. For students it serves as unit tester, versaitle to use over arbitrary toolchains through a generic JSON configuration language. For graders dragon-runner is an swiss army knife of sorts. It wraps scripts for building, gathering tests, and meta JSON configuration which are useful for herding an arbitrary number of compiler submissions into place. It also can run tests in a tournament mode, where each submitted compier and test-suite pair is ran in a cross product with every other submission. The tournament mode produces a CSV output according to the CMPUT 415 grading scheme. 

## Building 

Requires: `python >= 3.8`
To get `dragon-runner` on your CLI build the package and install it locally with pip.

```
git clone https://github.com/cmput415/Dragon-Runner.git
cd Dragon-Runner
pip install .
dragon-runner --help
```
If `dragon-runner` is not found on `$PATH` try adding `~/.local/bin`

## Contributing
Please feel free to make a PR. The previous tester had plenty of contributions
from students, we hope dragon-runner will as well.

## Examples

#### Preparing a Configuration File
The configuration file is in JSON format:
```json
{
  "testDir": "<path_to_input>",
  "testedExecutablePaths": {
    "ccid_or_groupid": "<path_to_executable>"
  },
  "runtimes": {
    "ccid_or_groupid": "<path_to_SHARED_library>"
  },
  "toolchains": {
    "toolchain_name": [
      {
        "stepName": "step 1",
        "executablePath": "<path_to_executable>",
        "arguments": ["arg1", "arg2", ...],
        "output": "<output_file_name>",
        "usesRuntime": true,
        "usesInStr": true
      }
    ]
  }
}
```
## Running

Dragon runner implements the same config semantics as the [415-tester](https://github.com/cmput415/Tester). Reference the documentation there in lieu of a complete migration.

## Issues

For any bugs or other problems please file a github issue.

