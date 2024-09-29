import pytest
import os
from pathlib import Path
from dragon_runner.config import load_config, Config

## ======== CONFIG UTIL ============ ##
def get_config_path(config_name: str) -> Path:
    cur_dir = Path(__file__).parent
    return cur_dir / "configs" / config_name

def load_config_by_name(config_name: str) -> Config:
    config_path = get_config_path(config_name)
    return load_config(str(config_path))

## ======== CONFIG FIXTURES ======== ##

@pytest.fixture(scope="session")
def config_factory():
    def _config_factory(config_name: str) -> Config:
        return load_config_by_name(config_name)
    return _config_factory

@pytest.fixture(scope="session")
def sample_valid_config(config_factory):
    return config_factory("gccConfig.json")

@pytest.fixture(scope="session")
def sample_valid_fail_config(config_factory):
    return config_factory("gccFailConfig.json")

@pytest.fixture(scope="session")
def sample_invalid_dir_config(config_factory):
    return config_factory("invalidDirConfig.json")

@pytest.fixture(scope="session")
def sample_invalid_exe_config(config_factory):
    return config_factory("invalidExeConfig.json")
