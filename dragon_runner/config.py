import json
import os
from typing                     import Dict, List
from dragon_runner.testfile     import TestFile
from dragon_runner.errors       import ConfigError, Verifiable, ErrorCollection
from dragon_runner.toolchain    import ToolChain
from dragon_runner.utils        import resolve_path

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
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'binary': self.binary,
            'env': self.env,
            'isBaseline': self.is_baseline
        }

class Config:
    def __init__(self, config_data: Dict):
        self.test_dir       = resolve_path(config_data['testDir'])
        self.executables    = self.parse_executables(config_data['executables'])
        self.toolchains     = self.parse_toolchains(config_data['toolchains'])
        self.errors         = self.verify()

    def parse_executables(self, executables_data: List[Dict]) -> List[Executable]:
        return [Executable(**exe) for exe in executables_data]
    
    def parse_toolchains(self, toolchains_data: Dict[str, List[Dict]]) -> List[ToolChain]:
        return [ToolChain(name, steps) for name, steps in toolchains_data.items()]
        
    def verify(self) -> ErrorCollection:
        errors = ErrorCollection()
        if not os.path.exists(self.test_dir):
            errors.add(ConfigError(f"Cannot find test directory: {self.test_dir}")) 
         
        for exe in self.executables:
            errors.extend(exe.verify().errors)       
        for tc in self.toolchains:
            errors.extend(tc.verify().errors)
        
        return errors

    def to_dict(self) -> Dict:
        return {
            'testDir': self.test_dir,
            'executables': [exe.to_dict() for exe in self.executables],
            'toolchains': {tc.name: tc.to_dict()[tc.name] for tc in self.toolchains}
        }
   
    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

def load_config(file_path: str) -> Config:
    """
    Load and parse the JSON configuration file.
    """
    with open(file_path, 'r') as config_file:
        config_data = json.load(config_file)
    return Config(config_data)

def gather_tests(test_dir: str) -> List[TestFile]:
    """
    Recursively gather all test files in the specified directory.
    A test file is any file that doesn't end with '.out' or '.ins'.
    """
    tests = []
    for root, _, files in os.walk(test_dir):
        for file in files:
            if not file.endswith(('.out', '.ins')):             
                test_path = os.path.join(root, file)
                #try:
                tests.append(TestFile(test_path))
                #except:
                #    print("Bad test: ", test_path)
    return tests

