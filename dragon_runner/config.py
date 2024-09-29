import json
import os
import pathlib
from typing                     import Dict, List, Optional
from dragon_runner.testfile     import TestFile
from dragon_runner.errors       import ConfigError, Verifiable, ErrorCollection
from dragon_runner.toolchain    import ToolChain
from dragon_runner.utils        import resolve_relative_path
from dragon_runner.log          import log

class SubPackage():
    def __init__(self, dir_path: str):
        self.dir_path: str          = dir_path
        self.rel_dir_path: str      = os.path.relpath(dir_path)
        self.tests: List[TestFile]  = self.gather_tests()
 
    def gather_tests(self) -> List[TestFile]:
        tests = []
        for file in os.listdir(self.dir_path):
            test_path = os.path.join(self.dir_path, file)
            if os.path.isfile(test_path) and not file.endswith(('.out', '.ins'))\
                                         and not file.startswith('.'):
                tests.append(TestFile(test_path))
        return tests 

class Executable(Verifiable):
    def __init__(self, id: str, exe_path: str, runtime: str):
        self.id         = id
        self.exe_path   = exe_path 
        self.runtime    = runtime 
        self.errors     = self.verify()

    def verify(self) -> ErrorCollection:
        errors = ErrorCollection()
        if not os.path.exists(self.exe_path):
            errors.add(ConfigError(f"Cannot find binary file: {self.exe_path}\
                                     in Executable: {self.id}"))
        return errors
    
    def source_env(self):
        """
        Source all env variables defined in this executables map
        TODO: update the JSON config to make env variables first class 
        """
        if self.runtime:
            runtime_path = pathlib.Path(self.runtime) 
            os.environ["LD_PRELOAD"] = str(runtime_path) 
            os.environ["RT_PATH"] = str(runtime_path.parent)
            if runtime_path.suffix.endswith(".so"):
                os.environ["RT_LIB"] = runtime_path.stem.removeprefix('lib').removesuffix(".so") 
            else:
                os.environ["RT_LIB"] = runtime_path.stem.removeprefix('lib').removesuffix(".dynlib") 

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'exe_path': self.exe_path
        }

class Config:
    def __init__(self, config_path: str, config_data: Dict):
        self.config_path        = config_path
        self.test_dir           = resolve_relative_path(config_data['testDir'], 
                                                        os.path.dirname(config_path))
        self.executables        = self.parse_executables(config_data['testedExecutablePaths'],
                                                         config_data.get('runtimes', ""))
        self.toolchains         = self.parse_toolchains(config_data['toolchains'])
        self.error_collection   = self.verify()
        self.sub_packages       = self.gather_subpackages()
    
    def parse_executables(self, executables_data: Dict[str, str],
                                runtimes_data: Dict[str, str]) -> List[Executable]: 
        def find_runtime(id) -> str:
            if not runtimes_data:
                return ""
            for key, value in runtimes_data.items():
                if key == id :
                    return value
            return ""

        return [Executable(id, path, find_runtime(id)) for id, path in executables_data.items()]
    
    def parse_toolchains(self, toolchains_data: Dict[str, List[Dict]]) -> List[ToolChain]:
        return [ToolChain(name, steps) for name, steps in toolchains_data.items()]

    def gather_subpackages(self) -> List[SubPackage]:
        subpackages = []
        for root, dirs, _ in os.walk(self.test_dir):
            for dir in dirs:
                subpkg_path = os.path.join(root, dir)
                subpackages.append(SubPackage(subpkg_path))
        return subpackages 
    
    def log_test_info(self):
        """Prints a simple formatted table of test information."""
        log("Test file"+ ' '*22 + "Expected bytes  Stdin bytes")
        log("-" * 60)
        for sp in self.sub_packages:
            log(f"Sub Package: {sp.rel_dir_path} ({len(sp.tests)} tests)")

    def verify(self) -> ErrorCollection:
        ec = ErrorCollection()
        if not os.path.exists(self.test_dir):
            ec.add(ConfigError(f"Cannot find test directory: {self.test_dir}"))  
        for exe in self.executables:
            ec.extend(exe.verify().errors)       
        for tc in self.toolchains:
            ec.extend(tc.verify().errors)
        return ec

    def to_dict(self) -> Dict: 
        return {
            'testDir': self.test_dir,
            'executables': [exe.to_dict() for exe in self.executables],
            'toolchains': {tc.name: tc.to_dict()[tc.name] for tc in self.toolchains},
            'subpackages': [os.path.basename(subpkg.subpkg_path) for subpkg in self.subpackages]
        }
    
    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

def load_config(config_path: str) -> Optional[Config]:
    """
    Load and parse the JSON configuration file.
    """
    if not os.path.exists(config_path):
        return None
    # try:
    with open(config_path, 'r') as config_file:
        config_data = json.load(config_file)
    return Config(config_path, config_data)
    # except Exception as e:
    #     log(f"Encountered unexpected filesystem error: {e}")
    #     return None
