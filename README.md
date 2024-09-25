# Serpent-Runner

Serpent-Runner is an experimental successor to the [415-tester](https://github.com/cmput415/Tester). Its name is derived by being a test runner written in python, for a compiler class that likes dragon iconography.

![Alt Text](/docs/logo-bg.png){width=300px}

Serpent-Runner inherits much of the previous testers design but with greater emphasis on the following aspects:

* Simplicity: Sub 1000 lines of heavily type hinted python.
* Reliability: Offer observability and verifibaility of each step throughout a tests transformation through the runner.
* User Experience: Better error handling, debug support and testfile flexbility.
* Design: Well defined points between the front, middle and backend.
* Speed: Serpent-Runner hands off the parallel work when python becomes a bottle neck. A multi-threaded C++ library is ready to churn through tests once their parameters have been resolved. 
