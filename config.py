import json
import os
from typing import Dict, List

class TestConfig:
    def __init__(self, config_data: Dict):
        self.test_dir = config_data['testDir']
        self.tested_executable_paths = config_data['testedExecutablePaths']
        self.solution_executable = config_data['solutionExecutable']
        self.runtimes = config_data.get('runtimes', {})
        self.toolchains = self._parse_toolchains(config_data['toolchains'])

    def _parse_toolchains(self, toolchains_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        parsed_toolchains = {}
        for toolchain_name, steps in toolchains_data.items():
            parsed_steps = []
            for step in steps:
                parsed_step = {
                    'stepName': step['stepName'],
                    'executablePath': step['executablePath'],
                    'arguments': step['arguments'],
                    'output': step.get('output', "-"),
                    'allowError': step.get('allowError', False),
                    'usesInStr': step.get('usesInStr', False),
                    'usesRuntime': step.get('usesRuntime', False)
                }
                parsed_steps.append(parsed_step)
            parsed_toolchains[toolchain_name] = parsed_steps
        return parsed_toolchains

    def to_dict(self) -> Dict:
        return {
            'test_dir': self.test_dir,
            'tested_executable_paths': self.tested_executable_paths,
            'solution_executable': self.solution_executable,
            'runtimes': self.runtimes,
            'toolchains': self.toolchains
        }

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2)

def load_config(file_path: str) -> TestConfig:
    """
    Load and parse the JSON configuration file.
    """
    with open(file_path, 'r') as config_file:
        config_data = json.load(config_file)
    return TestConfig(config_data)

def gather_tests(test_dir: str) -> List[str]:
    """
    Recursively gather all test files in the specified directory.
    A test file is any file that doesn't end with '.out' or '.ins'.
    """
    test_files = []
    for root, _, files in os.walk(test_dir):
        for file in files:
            if not file.endswith(('.out', '.ins')):
                relative_path = os.path.relpath(os.path.join(root, file), test_dir)
                test_files.append(relative_path)
    
    return sorted(test_files)

