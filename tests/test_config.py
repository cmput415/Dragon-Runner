import os
from dragon_runner.config import Config

def test_valid_config(sample_valid_config: Config): 
    conf = sample_valid_config 
    assert conf is not None
    assert conf.test_dir is not None
    assert conf.packages is not None
    for pkg in conf.packages:
        assert pkg.subpackages is not None
        for spkg in pkg.subpackages:
            assert spkg is not None
            assert len(spkg.tests) > 0

    assert sample_valid_config.error_collection == False
    assert os.path.exists(sample_valid_config.test_dir)

def test_invalid_dir_config(sample_invalid_dir_config):
    assert sample_invalid_dir_config.error_collection == True
    assert not os.path.exists(sample_invalid_dir_config.test_dir)

def test_invalid_exe_config(sample_invalid_exe_config):
    assert sample_invalid_exe_config.error_collection == True
    assert len(sample_invalid_exe_config.executables) == 1
    assert not os.path.exists(sample_invalid_exe_config.executables[0].exe_path)
