import pytest
import os
from dragon_runner.testfile import TestFile
from dragon_runner.config   import Config 
from dragon_runner.config import load_config 

@pytest.fixture(scope="session")
def sample_test_file():    
    return TestFile("path/to/sample/test.c")

@pytest.fixture(scope="session")
def sample_config():
    return Config({"testDir": "path/to/tests", "executables": [], "toolchains": {}})

## ======== CONFIG UTIL ============ ##
def get_valid_config_path():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(cur_dir,"configs/gccConfig.json")

def get_invalid_dir_conifg_path():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(cur_dir,"configs/invalidDirConfig.json")

def get_invalid_exe_conifg_path():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(cur_dir,"configs/invalidExeConfig.json")

## ======== CONFIG FIXTURES ======== ##

@pytest.fixture(scope="session")
def sample_valid_config(): 
    return load_config(get_valid_config_path())

@pytest.fixture(scope="session")
def sample_invalid_dir_config():
    return load_config(get_invalid_dir_conifg_path())
 
@pytest.fixture(scope="session")
def sample_invalid_exe_config():
    return load_config(get_invalid_exe_conifg_path())
      