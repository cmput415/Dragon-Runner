# Dragon-Runner

Dragon-Runner is a successor to the [415-tester](https://github.com/cmput415/Tester). Its name is derrived from being a test runner for a compiler class that likes dragon iconography.

<div align="center">
  <div style="background-color: #f0f0f0; border-radius: 10px; padding: 20px; display: inline-block;"> 
    <img alt="Dragon-Runner Logo" src="/docs/logo-new.png" width="250">
  </div>
</div>
<br>

Dragon-Runner inherits much of the previous testers design but with greater emphasis on the following aspects:

* Simplicity: Sub 1000 lines
* Reliability: Offer observability and verifibaility of each step throughout a tests transformation through the runner.
* User Experience: Warn when paths do not exist in the config, throw more informed errors when toolchains panic and improve debug support.
* Design: Define clear boundaries between the front, middle and backend.
* Speed: When python becomes a bottle neck, a multi-threaded dynamic library is ready to churn through tests in parallel (TODO).

## Building 

To get `dragon-runner` on your CLI build the package and install it locally with pip.

```
git clone https://github.com/cmput415/Dragon-Runner.git
cd Dragon-Runner
pip install -e .
dragon-runner --help
```
If `dragon-runner` is not found on `$PATH` try adding `~/.local/bin`
