import os
from dragon_runner.config import Config

def test_valid_config(config_factory): 
    config = config_factory("gccPassConfig.json")
    
    assert config is not None
    assert config.test_dir is not None
    assert config.packages is not None
    for pkg in config.packages:
        assert pkg.subpackages is not None
        for spkg in pkg.subpackages:
            assert spkg is not None
            assert len(spkg.tests) > 0

    assert config.error_collection == False
    assert os.path.exists(config.test_dir)

def test_invalid_dir_config(config_factory):
    config = config_factory("invalidDirConfig.json")
    
    assert config.error_collection == True
    assert not os.path.exists(config.test_dir)

def test_invalid_exe_config(config_factory):
    
    config = config_factory("invalidExeConfig.json")

    assert config.error_collection == True
    assert len(config.executables) == 1
    assert not os.path.exists(config.executables[0].exe_path)
