import os
import sys
from io import BytesIO
from dragon_runner.utils import bytes_to_str

class Logger:
    def __init__(self):
        self.debug_level = self._get_debug_level()

    def _get_debug_level(self):
        return int(os.environ.get('DEBUG', '0')) 

    def log(self, level, indent, *args, **kwargs):
        prefix = ' '*indent
        if self.debug_level >= level:
            print(prefix, *args, **kwargs) 

_logger_instance = None

def get_logger():
    """
    get singleton logger for the entire program
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance

def log_multiline(content: str, level=0, indent=0, **kwargs):
    """
    Log multiline content with proper indentation
    """
    for line in str(content).splitlines():
        log(line.rstrip(), level=level, indent=indent, **kwargs)

def log(*args, level=0, indent=0, **kwargs):
    get_logger().log(level, indent, *args, **kwargs)

def log_delimiter(title: str, level=0, indent=0):
    delimiter = '-' * 20
    log(delimiter + ' ' + title + ' ' + delimiter, level=level, indent=indent)

def log_bytes(bytes: BytesIO, level=0, indent=0):
    bytes_str = bytes_to_str(bytes)
    log_multiline(str(bytes_str), level=level, indent=indent)