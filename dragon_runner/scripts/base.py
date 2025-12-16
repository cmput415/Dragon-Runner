from abc import ABC, abstractmethod
import argparse
from typing import List

class Script(ABC):
    """
    Base class for all dragon-runner scripts.
    Provides a standard interface for script metadata and execution.
    """
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the script name (e.g., 'build.py')"""
        pass

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        """Return a brief description of what the script does"""
        pass

    @classmethod
    @abstractmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        """Return the argument parser for this script"""
        pass

    @classmethod
    def usage(cls) -> str:
        """Generate usage string from the parser"""
        parser = cls.get_parser()
        usage_lines = parser.format_help().split('\n')
        if usage_lines and usage_lines[0].startswith('usage:'):
            parts = usage_lines[0].split(None, 2)
            rest = parts[2] if len(parts) > 2 else ''
            usage_lines[0] = f"usage: dragon-runner script {cls.name()} {rest}"
        return '\n'.join(usage_lines)

    @classmethod
    @abstractmethod
    def main(cls, args: List[str]) -> int: 
        pass

