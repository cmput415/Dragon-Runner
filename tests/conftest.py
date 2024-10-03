import pytest
from pathlib import Path
from dragon_runner.config import load_config, Config
from dragon_runner.cli import CLIArgs

def get_config_path(config_name: str) -> Path:
    return Path(__file__).parent / "configs" / config_name

def create_config(config_name: str) -> Config:
    config_path = get_config_path(config_name)
    return load_config(str(config_path))

def create_cli_args(**kwargs) -> CLIArgs:
    return CLIArgs(
        kwargs.get('config_file', None),
        kwargs.get('grade_file', None),
        kwargs.get('failure_file', None),
        kwargs.get('timeout', None),
        kwargs.get('debug-package', None),
        kwargs.get('time', None),
        kwargs.get('verbosity', None),
        kwargs.get('verify', None)
    )

@pytest.fixture(scope="session")
def config_factory():
    return create_config

@pytest.fixture(scope="session")
def cli_factory():
    return create_cli_args
