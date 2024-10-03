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
    """
    Represents a set of tests in a directory
    """
    def __init__(self, path: str): 
        self.path: str              = path
        self.name: str              = os.path.basename(path)
        self.tests: List[TestFile]  = self.gather_tests()

    @staticmethod
    def is_test(test_path: str):
        """
        Ignore reserved output and input stream extensions and hidden files
        """
        return (os.path.isfile(test_path) and
                not os.path.basename(test_path).startswith('.') and
                not test_path.endswith(('.out', '.ins')))

    def gather_tests(self) -> List[TestFile]:
        """
        Find all tests in the directory of the subpackage.
        """
        tests = []
        for file in os.listdir(self.path):
            test_path = os.path.join(self.path, file)
            if self.is_test(test_path):
                tests.append(TestFile(test_path))
        return tests 

class Package():
    """
    Represents a single test package. Shoud have a corresponding CCID if submitted. 
    """
    def __init__(self, path: str):
        self.path: str      = path
        self.name: str      = os.path.basename(path)
        self.n_tests        = 0
        self.subpackages    = [] 
        self.gather_subpackages()

    def add_subpackage(self, spkg: SubPackage):
        """
        Add a subpackage while keeping total test count up to date
        """
        self.n_tests += len(spkg.tests)
        self.subpackages.append(spkg)

    def gather_subpackages(self) -> List[SubPackage]:
        """
        Collect any directory within a package and create a subpackage.
        """
        subpackages = []
        for parent_path, dirs, files in os.walk(self.path):
            top_level_spkg = SubPackage(parent_path) 
            if len(top_level_spkg.tests) > 0:
                self.add_subpackage(top_level_spkg)
            for dirname in dirs:
                spkg = SubPackage(os.path.join(parent_path, dirname))
                if len(spkg.tests) > 0:
                    self.add_subpackage(spkg)
        return subpackages

class Executable(Verifiable):
    """
    Represents a single tested executable along with an optional associated runtime.
    """
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
    """
    An in memory representation of the JSON configuration file which directs the tester. 
    """
    def __init__(self, config_path: str, config_data: Dict):
        self.config_path        = config_path
        self.test_dir           = resolve_relative_path(config_data['testDir'], 
                                                        os.path.dirname(config_path))
        self.executables        = self.parse_executables(config_data['testedExecutablePaths'],
                                                         config_data.get('runtimes', ""))
        self.solution_exe       = config_data.get('solutionExecutable', None)
        self.toolchains         = self.parse_toolchains(config_data['toolchains'])
        self.error_collection   = self.verify()
        self.packages           = self.gather_packages()
    
    def parse_executables(self, executables_data: Dict[str, str],
                                runtimes_data: Dict[str, str]) -> List[Executable]:
        """
        Parse each executable and assign a corresponding runtime if supplied
        """
        def find_runtime(id) -> str:
            if not runtimes_data:
                return ""
            for key, value in runtimes_data.items():
                if key == id :
                    return value
            return ""
        return [Executable(id, path, find_runtime(id)) for id, path in executables_data.items()]
    
    def parse_toolchains(self, toolchains_data: Dict[str, List[Dict]]) -> List[ToolChain]:
        """
        Parse each toolchain from the config file and return a list of them.
        """
        return [ToolChain(name, steps) for name, steps in toolchains_data.items()]

    def gather_packages(self) -> List[Package]:
        """
        Collect all top-level directories in testdir and create a package
        """ 
        packages = []
        for parent_path, dirs, _ in os.walk(self.test_dir):
            for dirname in dirs:
                pkg_path = os.path.join(parent_path, dirname)
                packages.append(Package(pkg_path))
            break
        return packages

    def log_test_info(self):
        """
        Prints a simple formatted table of test information.
        """
        for pkg in self.packages:
            log(f"-- ({pkg.name})", level=1)
            for spkg in pkg.subpackages:
                log(f"  -- ({spkg.name})", level=2)
                for test in spkg.tests:
                    log(f"    -- ({test.file})", level=3)

    def verify(self) -> ErrorCollection:
        """
        Assert valid paths and that all compositetoolchains and executables also verify.
        """
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
            'subpackages': [pkg.name for pkg in self.packages]
        }
    
    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

def load_config(config_path: str) -> Optional[Config]:
    """
    Load and parse the JSON configuration file.
    """
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)
        return Config(config_path, config_data)
    except Exception as e:
        log(f"Failed to create the JSON configuration with error: {e}")
        return None
