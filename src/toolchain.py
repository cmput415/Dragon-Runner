import json
from typing import Dict, List, Iterator, Optional
from errors import ConfigError

class Step:
    def __init__(self, **kwargs):
        self.name           = kwargs.get('stepName', None)
        self.command        = kwargs.get('command', None)
        self.arguments      = kwargs.get('arguments', None)
        self.output         = kwargs.get('output', None)
        self.allow_error    = kwargs.get('allowError', False)
        self.uses_ins       = kwargs.get('usesInStr', False)
        self.uses_runtime   = kwargs.get('usesRuntime', False)
    
    def verify(self) -> Optional[ConfigError]:
        return None

    def to_dict(self) -> Dict:
        return {
            'stepName': self.name,
            'command': self.command,
            'arguments': self.arguments,
            'output': self.output,
            'allowError': self.allow_error,
            'usesInStr': self.uses_ins,
            'usesRuntime': self.uses_runtime
        }

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2)

class ToolChain:
    def __init__(self, name: str, steps: List[Step]):
        self.name = name
        self.steps = steps
    
    def verify(self) -> Optional[ConfigError]:
        errors = ConfigError()
        for step in self.steps:
            if error := step.verify():
                errors.add(error)
        return errors if errors else None
    
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

