import json
import os
from typing import Dict, List, Optional
from test import Test
from errors import ConfigError
from toolchain import ToolChain, Step
from dataclasses import dataclass

class Executable:
    def __init__(self, **kwargs):
        self.id             = kwargs['id']
        self.binary         = kwargs['binary']
        self.env            = kwargs.get('env', {})
        self.is_baseline    = kwargs.get('isBaseline', False)
         
    def verify(self) -> Optional[ConfigError]:
        if not os.path.exists(self.binary):
            return ConfigError(f"Can not find binary file: {self.binary}")
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'binary': self.binary,
            'env': self.env,
            'isBaseline': self.is_baseline
        }

class Config:
    def __init__(self, config_data: Dict):
        self.test_dir       = config_data['testDir']
        self.executables    = self.parse_executables(config_data['executables'])
        self.toolchains     = self.parse_toolchains(config_data['toolchains'])

    def parse_executables(self, executables_data: List[Dict]) -> List[Executable]:
        return [Executable(**exe) for exe in executables_data]

    def parse_toolchains(self, toolchains_data: Dict[str, List[Dict]]) -> List[ToolChain]:
        parsed_toolchains = []
        for toolchain_name, steps in toolchains_data.items():
            parsed_steps = [Step(**step) for step in steps]
            parsed_toolchains.append(ToolChain(toolchain_name, parsed_steps))

        return parsed_toolchains

    def verify(self) -> Optional[ConfigError]:
        errors = ConfigError() 
        if not os.path.exists(self.test_dir):
            errors.add(f"Cannot find test directory: {self.test_dir}") 
        
        for exe in self.executables:
            if error := exe.verify():
                errors.add(error)  
        
        for tc in self.toolchains:
            if error := tc.verify():
                errors.add(error)
        
        errors.add(f"CONFIG_ERROR: This is a test error") 
        return errors if errors.errors else None

    def to_dict(self) -> Dict:
        return {
            'testDir': self.test_dir,
            'executables': [exe.to_dict() for exe in self.executables],
            'toolchains': {tc.name: tc.to_dict()[tc.name] for tc in self.toolchains}
        }
   
    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2)

def load_config(file_path: str) -> Config:
    """
    Load and parse the JSON configuration file.
    """
    with open(file_path, 'r') as config_file:
        config_data = json.load(config_file)
    return Config(config_data)

def gather_tests(test_dir: str) -> List[Test]:
    """
    Recursively gather all test files in the specified directory.
    A test file is any file that doesn't end with '.out' or '.ins'.
    """
    tests = []
    for root, _, files in os.walk(test_dir):
        for file in files:
            if not file.endswith(('.out', '.ins')):             
                test_path = os.path.join(root, file)
                try:
                    tests.append(Test(test_path))
                except:
                    print("Bad test: ", test_path)
    return tests

