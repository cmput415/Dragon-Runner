import pytest
import tempfile
import os
from dragon_runner.config import gather_tests

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

@pytest.fixture
def get_C_tests():
    c_package = os.path.join(os.path.dirname(__file__), "packages", "CPackage")
    return gather_tests(c_package)
