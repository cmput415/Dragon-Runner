import json
import os
import subprocess
from typing import Dict, List, Iterator
from dragon_runner.src.errors import *

class Step(Verifiable):
    def __init__(self, **kwargs):
        self.name           = kwargs.get('stepName', None)
        self.exe_path       = kwargs.get('executablePath', None)
        self.arguments      = kwargs.get('arguments', None)
        self.output         = kwargs.get('output', None)
        self.allow_error    = kwargs.get('allowError', False)
        self.uses_ins       = kwargs.get('usesInStr', False)
        self.uses_runtime   = kwargs.get('usesRuntime', False)
    
    def verify(self) -> ErrorCollection:
        errors = ErrorCollection()
        if not self.name:
            errors.add(ConfigError(f"Missing required filed 'stepName' in Step {self.name}"))
        
        if not self.exe_path:
            errors.add(ConfigError(f"Missing required field 'exe_path' in Step: {self.name}"))

        elif not os.path.exists(self.exe_path) and not self.exe_path.startswith('$'):
            errors.add(ConfigError(f"Cannot find exe_path '{self.exe_path}' in Step: {self.name}"))
        
        return errors 

    def to_dict(self) -> Dict:
        return {
            'stepName': self.name,
            'exe_path': self.exe_path,
            'arguments': self.arguments,
            'output': self.output,
            'allowError': self.allow_error,
            'usesInStr': self.uses_ins,
            'usesRuntime': self.uses_runtime
        }

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2)

class ToolChain(Verifiable):
    def __init__(self, name: str, steps: List[Dict]):
        self.name       = name
        self.steps      = [Step(**step) for step in steps]
    
    def verify(self) -> ErrorCollection:
        errors = ErrorCollection()
        for step in self.steps:
            errors.extend(step.verify().errors)
        return errors

    def to_dict(self) -> Dict[str, List[Dict]]:
        return {self.name: [step.to_dict() for step in self.steps]}

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2)
    
    def __iter__(self) -> Iterator[Step]:
        return iter(self.steps)

    def __len__(self) -> int:
        return len(self.steps)

    def __getitem__(self, index: int) -> Step:
        return self.steps[index]
