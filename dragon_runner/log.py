import os
import sys

class Logger:
    def __init__(self):
        self.debug_level = self._get_debug_level()

    def _get_debug_level(self):
        return int(os.environ.get('DEBUG', '0'))

    def log(self, level, *args, **kwargs):
        if self.debug_level >= level:
            if level == 0:
                print(*args, file=sys.stderr, **kwargs)
            else:
                prefix = f"[DEBUG {level}]"
                print(prefix, *args, file=sys.stderr, **kwargs)

_logger_instance = None

def get_logger():
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance

def log(*args, level=0, **kwargs):
    get_logger().log(level, *args, **kwargs)

