<div align="center">

# Dragon-Runner
#### A Custom Test Runner for CMPUT 415
<div style="background-color: #f0f0f0; border-radius: 10px; padding: 10px; display: inline-block;"> 
  <img alt="Dragon-Runner Logo" src="/docs/runner-log.png" width="80">
</div>
</div>
<br>

## What is Dragon-Runner

`dragon-runner` is the testing utiliy for CMPUT 415, Copmiler Design which provides utility for both students and graders. It is a rewrite of the [415-tester](https://github.com/cmput415/Tester), with improved marking utilites and ergonomics. For students, `dragon-runner`serves as unit tester which can be configured for arbitrary toolchains through the JSON configuration language. For graders `dragon-runner` wraps scripts for building, gathering tests and grading submissions, making it useful for herding an arbitrary number of compiler submissions into place. It's primary function is to run tests in a tournament mode. In the grading tournament, each submitted compiler (defender) and test-suite (attacker) is ran in a cross product. The tournament mode produces a CSV output according to the CMPUT 415 grading scheme. 

## Building 

Requires: `python >= 3.8`
To get `dragon-runner` on your CLI build the package and install it locally with pip.

```
git clone https://github.com/cmput415/Dragon-Runner.git
cd Dragon-Runner
pip install .
dragon-runner --help
```
If `dragon-runner` is not found on `$PATH` ensure `~/.local/bin` is exposed.

## Confugration
`dragon-runner` uses a JSON configuration language to orchestrate tests and toolchains. Below is an example of running `gcc` 

```json
{
  "testDir": "../packages/CPackage",
  "testedExecutablePaths": {
    "gcc": "/usr/bin/gcc"
  },
  "toolchains": {
    "GCC-toolchain": [
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

### Config Properties

* `testDir`: Path to the module contains packages of testfiles.
* `testedExecutablePaths`: A list of executable paths to be tested. Ensure ccid_or_groupid matches your test package name.
* `runtimes`: A list of shared libraries to be loaded before a command is executed. (OPTIONAL)
* `solutionExecutable`: A string indicating which executable among the tested exectuables in the reference solution. (OPTIONAL).
* `toolchains`: A list of toolchains defining steps to transform input files to expected output files.
  * `stepName`: Name of the step (e.g., `generator` or `arm-gcc`).
  * `executablePath`: Path to the executable for this step. Use `$EXE` for the tested executable or `$INPUT` for the output of the previous step.
  arguments: List of arguments for the executable. `$INPUT` and `$OUTPUT` resolve to input and output files.
  * `output`: Use a named file to feed into the next commands input. Overrides using the stdout produced by the command. Useful for commands for which the output to be further transformed is a file like `Clang` or any of the 415 assignments.
  * `usesRuntime`: Will set environment variables `LD_LIBRARY_PATH` to equal `$RT_PATH` and `LD_PRELOAD` equal to `runtime`. Useful for `llc` and `lli` toolchains respectively. (OPTIONAL)
  * `usesInStr`: Boolean to replace stdin with the file stream from the `testfile`. (OPTIONAL)
  * `allowError`: Boolean which if true will allow the toolchain to tolerate non-zero exit codes from commmands, causing the premature termination of the toolchain and diff on `stderr` rather than `stdout`. (OPTIONAL)

### Automatic Variables
Automatic variables may be provided in the arguments of a toolchain step and are resolved by the tester.
* `$INPUT`: For the first step, `$INPUT` is the testfile. For any following step `$INPUT` is the file alised by previous steps `$OUTPUT`.
* `$OUTPUT`: Refers to the file a successor command will use as `$INPUT`. Defaults to an anonymous file in `/tmp` that is filled with the commands stdout.
            If the `output` property is defined then `$OUTPUT` resolves to the provided file. 
* `$RT_PATH`: Resolves the path of the current `runtime` shared object -- if one is provided. For example given the property: ```runtimes: { /path/lib/libfoo.so }```, `$RT_PATH` resolves to `/path/lib`. This
is useful for providing the dynamic library path at link time to clang when using an `llc` based toolchain for `LLVM`. 
* `$RT_LIB`: Similarly to `$RT_PATH` resolves to the library name of the provided runtime. Acoording to the previous example `$RT_LIB` resolves to `foo`. Also useful in the clang step of an `llc` toolchain. See the runtime tests for a clear example. 

### Testfile
Inside a test, the standard input stream and expected output may be supplied *within* the file using comments. All directives are sensitive to whitespace and do not insert newlines between themselves by default. For example, `INPUT: a a a` is equivalent to a file with three whitespace characters, three `'a'` characters and no newline for a total of `6 bytes`.  

 * `INPUT:` Direct a single line of text to `stdin`. Not newline terminated.
 * `INPUT_FILE:` Supply a relative or absolute path to a `.ins` file. Useful if testing for escape characters or long, cumbersome inputs.

 * `CHECK:` Direct a single line of text to `stdout` that the program is expected to output. Not newline terminated.
 * `CHECK_FILE:` Supply a relative or absolute path to a `.out` file.  

Finally, an arbitrary number of `INPUT` and `CHECK` directives may be supplied in a file, and an `INPUT` and
`INPUT_FILE` directive may not co-exist. 
```
// This is a commnent.
// INPUT:a

procedure main() returns integer {
  character c;
  c <- std_input;
  c -> std_output; 
}

// CHECK:a
```
If you find youreself confused about `INPUT` and `CHECK` take a peek into `/tests` where valid and invalid testfiles can be found. Otherwise, falling back onto `INPUT_FILE` and `CHECK_FILE` is perfectly fine.

## Running
For students: 
`dragon-runner <OPTIONS> <CONFIG_JSON>`

For graders:
`dragon-runner {tournament|memcheck|script} <ARGS...>`

## Issues
For any bugs or other problems please file a github issue.

## Contributing
Please feel free to make a PR, the previous tester had plenty of contributions from students.


