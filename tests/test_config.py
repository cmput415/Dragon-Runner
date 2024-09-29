import os

def test_valid_config(sample_valid_config): 
    assert sample_valid_config is not None
    assert sample_valid_config.test_dir is not None
    assert sample_valid_config.tests is not None
    assert sample_valid_config.error_collection == False
    assert os.path.exists(sample_valid_config.test_dir)

def test_invalid_dir_config(sample_invalid_dir_config):
    assert sample_invalid_dir_config.error_collection == True
    assert not os.path.exists(sample_invalid_dir_config.test_dir)

def test_invalid_exe_config(sample_invalid_exe_config):
    assert sample_invalid_exe_config.error_collection == True
    assert len(sample_invalid_exe_config.executables) == 1
    assert not os.path.exists(sample_invalid_exe_config.executables[0].exe_path)
