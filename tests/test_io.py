import pytest
import os
from dragon_runner.testfile import TestFile
from dragon_runner.config import gather_tests 

def test_test_creation(get_C_tests):
    c_tests = get_C_tests
    assert c_tests is not None
    for test in c_tests:
        print(test)

def test_gather_tests(temp_dir):
    open(os.path.join(temp_dir, 'test1.c'), 'w').close()
    open(os.path.join(temp_dir, 'test2.c'), 'w').close()
    open(os.path.join(temp_dir, 'not_a_test.out'), 'w').close()
    
    tests = gather_tests(temp_dir)
    
    assert len(tests) == 2
    assert all(isinstance(test, TestFile) for test in tests)
    assert set(test.stem for test in tests) == {'test1', 'test2'}
