# Dragon-Runner

Dragon-Runner is an experimental successor to the [415-tester](https://github.com/cmput415/Tester). Its name is derived by being a test runner written in python, for a compiler class that likes dragon iconography.

<p align="center">
  <img src="/docs/logo-bg.png" alt="Alt text for the image", width=400>
</p>

Dragon-Runner inherits much of the previous testers design but with greater emphasis on the following aspects:

* Simplicity: Sub 1000 lines of heavily type hinted python.
* Reliability: Offer observability and verifibaility of each step throughout a tests transformation through the runner.
* User Experience: Better error handling, debug support and testfile flexbility.
* Design: Well defined points between the front, middle and backend.
* Speed: When python becomes a bottle neck, a multi-threaded dynamic library is ready to churn through tests in parallel.

## Building 

To get `dragon-runner` on your CLI build the package and install it locally with pip.
```
python3 -m build
pip intsall -e .
dragon-runner --help
```

