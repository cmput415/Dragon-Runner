import json
import os
from typing                     import Dict, List, Optional
from dragon_runner.testfile     import TestFile
from dragon_runner.errors       import ConfigError, Verifiable, ErrorCollection
from dragon_runner.toolchain    import ToolChain
from dragon_runner.utils        import resolve_relative_path
from dragon_runner.log          import log

class Executable(Verifiable):
    def __init__(self, **kwargs):
        self.id             = kwargs['id']
        self.binary         = kwargs['binary']
        self.env            = kwargs.get('env', {})
        self.is_baseline    = kwargs.get('isBaseline', False)
        self.errors         = self.verify()
        
    def verify(self) -> ErrorCollection:
        errors = ErrorCollection()
        if not os.path.exists(self.binary):
            errors.add(ConfigError(f"Cannot find binary file: {self.binary}\
                                     in Executable: {self.id}"))
        return errors
    
    def source_env(self):
        """
        Source all env variables defined in this executables map
        """
        for key, value in self.env.items():
            os.environ[key] = value
 
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'binary': self.binary,
            'env': self.env,
            'isBaseline': self.is_baseline
        }

class Config:
    def __init__(self, config_path: str, config_data: Dict):
        self.config_path        = config_path
        self.test_dir           = resolve_relative_path(config_data['testDir'], 
                                                        os.path.dirname(config_path))
        self.executables        = self.parse_executables(config_data['executables'])
        self.toolchains         = self.parse_toolchains(config_data['toolchains'])
        self.error_collection   = self.verify()
        self.tests              = self.gather_tests()

    def parse_executables(self, executables_data: List[Dict]) -> List[Executable]:
        return [Executable(**exe) for exe in executables_data]
    
    def parse_toolchains(self, toolchains_data: Dict[str, List[Dict]]) -> List[ToolChain]:
        return [ToolChain(name, steps) for name, steps in toolchains_data.items()]
    
    def gather_tests(self) -> List[TestFile]:
        """
        Recursively gather all test files in the specified directory.
        A test file is any file that doesn't end with '.out' or '.ins'.
        """
        tests = []
        for root, _, files in os.walk(self.test_dir):
            for file in files:
                if not file.endswith(('.out', '.ins')):             
                    test_path = os.path.join(root, file)
                    tests.append(TestFile(test_path))
        return tests
    
    def log_test_info(self):
        """Prints a simple formatted table of test information."""
        log("Test file"+ ' '*22 + "Expected bytes  Stdin bytes")
        log("-" * 60)
        for test in self.tests:
            out_bytes = len(test.expected_out.getbuffer())
            ins_bytes = len(test.input_stream.getbuffer())
            log(f"{test.stem:<25} {out_bytes:>15} {ins_bytes:>12}")

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
            'toolchains': {tc.name: tc.to_dict()[tc.name] for tc in self.toolchains}
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
        log(f"Encountered unexpected filesystem error: {e}")
        return None
