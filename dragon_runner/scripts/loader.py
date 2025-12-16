import subprocess
import sys
import importlib
from typing import List, Dict, Type, Optional
from pathlib import Path
from dragon_runner.scripts.base import Script


class Loader:
    """
    Dragon runner allows grading scripts to be run through its CLI.
    Each script is executed as a subprocess using Python's -m flag to ensure
    consistent behavior whether called directly or through dragon-runner.
    """
    def __init__(self):
        self.script_modules = {
            "add_empty":     "dragon_runner.scripts.add_empty",
            "build":         "dragon_runner.scripts.build",
            "clean-build":   "dragon_runner.scripts.clean_build",
            "checkout":      "dragon_runner.scripts.checkout",
            "gather":        "dragon_runner.scripts.gather",
            "gen-config":    "dragon_runner.scripts.gen_config",
            "grade":         "dragon_runner.scripts.grade",
            "grade-perf":    "dragon_runner.scripts.grade_perf",
        }

    def _load_script_class(self, module_name: str) -> Optional[Type[Script]]:
        """
        Dynamically load a script module and return its Script class if it exists.
        Returns None if the module doesn't implement the Script interface.
        """
        try:
            module = importlib.import_module(module_name)
            # Look for a class that inherits from Script
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Script) and
                    attr is not Script):
                    return attr
        except Exception:
            pass
        return None

    def __call__(self, args: List[str]):
        """
        Select the script to run from the mode argument passed through
        dragon-runner CLI and execute it as a subprocess.
        """
        if args == [] or args[0] not in self.script_modules:
            print(self)
            return 1

        module = self.script_modules[args[0]]
        cmd = [sys.executable, "-m", module] + args
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except Exception as e:
            print(f"Failed to run script: {e}")
            return 1

    def __repr__(self):
        """
        Display all available scripts with their descriptions and usage.
        """
        s = "Available Scripts:\n"
        for script_name, module_name in self.script_modules.items():
            script_class = self._load_script_class(module_name)
            max_script = max(self.script_modules.keys(),key=lambda x: len(x))
            if script_class:
                s += f" * {script_name}: {(len(max_script) - len(script_name))* ' '} "
                s += f"{script_class.description()}\n"
        return s

