<div align="center">

# Dragon-Runner
#### A Custom Test Runner for CMPUT 415
<div style="background-color: #f0f0f0; border-radius: 10px; padding: 10px; display: inline-block;"> 
  <img alt="Dragon-Runner Logo" src="/docs/runner-log.png" width="90">
</div>
</div>
<br>

Dragon-Runner is a successor to the [415-tester](https://github.com/cmput415/Tester). Its name is derived by being a test runner for a compiler class that likes dragon iconography.

## Design
Dragon-Runner inherits much of the previous testers design but with greater emphasis on the following aspects:

* Simplicity: Sub 1000 lines
* Reliability: Each step of the toolchain is observable to a configurable degree.
* User Experience: Warn when paths do not exist in the config, throw more informed errors when toolchains panic and improve debug support.
* Design: Define clear boundaries between the front, middle and backend.

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


## Running

Dragon runner implements the same config semantics as the [415-tester](https://github.com/cmput415/Tester). Reference the documentation there in lieu of a complete migration.

## Contributing

Please feel free to make a PR. The previous tester had plenty of contributions from students. 
