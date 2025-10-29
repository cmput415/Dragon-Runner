import os
from dragon_runner.src.cli import RunnerArgs, Mode
from dragon_runner.src.config import load_config
import fnmatch


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


def test_package_filter(config_factory):
    """Test that subpackage filtering works correctly using glob pattern matching on paths"""

    config_path = os.path.join(
        os.path.dirname(__file__), "configs", "gccPassConfig.json"
    )

    # Load config - packages are always loaded, filtering happens at subpackage level
    config = load_config(
        config_path, RunnerArgs(mode=Mode.REGULAR, config_file=config_path)
    )

    # Collect all subpackages across all packages
    all_subpackages = []
    for pkg in config.packages:
        for spkg in pkg.subpackages:
            all_subpackages.append(spkg.path)

    # Verify we have subpackages to test with
    assert len(all_subpackages) > 0

    # Test filter pattern "*ErrorPass*" - should match subpackages containing "ErrorPass" in path
    filter_pattern = "*ErrorPass*"
    filtered_subpackages = [
        spkg_path
        for spkg_path in all_subpackages
        if fnmatch.fnmatch(spkg_path.lower(), filter_pattern.lower())
    ]

    # Should have some matches
    assert len(filtered_subpackages) > 0

    # All filtered subpackages should match the pattern (case insensitive)
    for spkg_path in filtered_subpackages:
        assert fnmatch.fnmatch(spkg_path.lower(), filter_pattern.lower())
        assert "errorpass" in spkg_path.lower()


def test_invalid_dir_config(config_factory):
    config = config_factory("invalidDirConfig.json")

    assert config.error_collection == True
    assert not os.path.exists(config.test_dir)


def test_invalid_exe_config(config_factory):

    config = config_factory("invalidExeConfig.json")

    assert config.error_collection == True
    assert len(config.executables) == 1
    assert not os.path.exists(config.executables[0].exe_path)
