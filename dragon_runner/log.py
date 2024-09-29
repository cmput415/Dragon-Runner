import os
import sys

class Logger:
    def __init__(self):
        self.debug_level = self._get_debug_level()

    def _get_debug_level(self):
        return int(os.environ.get('DEBUG', '0'))

    def log(self, level, indent, *args, **kwargs):
        prefix = ' '*indent
        if self.debug_level >= level:
            print(prefix, *args, file=sys.stderr, **kwargs)

_logger_instance = None

def get_logger():
    """
    get singleton logger for the entire program
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance

def log_multiline(content: str, indent: int):
    """
    Log multiline content with proper indentation
    """
    for line in content.splitlines():
        log(line.rstrip(), indent=indent)

def log(*args, level=0, indent=0, **kwargs):
    get_logger().log(level, indent, *args, **kwargs)

