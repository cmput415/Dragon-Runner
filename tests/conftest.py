import pytest
from typing import Optional
from pathlib import Path
from dragon_runner.src.cli import CLIArgs
from dragon_runner.src.config import load_config, Config

def get_config_path(config_name: str) -> Path:
    return Path(__file__).parent / "configs" / config_name

def create_config(config_name: str) -> Optional[Config]:
    config_path = get_config_path(config_name)
    return load_config(str(config_path))

def create_cli_args(**kwargs) -> CLIArgs:
    return CLIArgs(
        config_file     = kwargs.get('config_file', None),
        output     = kwargs.get('output_file', None),
        failure_log     = kwargs.get('failure_log', None),
        debug_package   = kwargs.get('debug_package', None),
        mode            = kwargs.get('mode', None),
        timeout         = kwargs.get('timeout', 5),
        time            = kwargs.get('time', None),
        verbosity       = kwargs.get('verbosity', None),
        verify          = kwargs.get('verify', None),
        script_args     = kwargs.get('script_args', None)
    )

@pytest.fixture(scope="session")
def config_factory():
    return create_config

@pytest.fixture(scope="session")
def cli_factory():
    return create_cli_args
