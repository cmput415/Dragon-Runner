import os
import sys
import time
import uuid
import shutil
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3

class Logger:
    def __init__(self):
        self.debug_level = self._get_debug_level()
        self.enable_timestamps = os.environ.get('DR_LOG_TIMESTAMPS', 'true').lower() == 'true'
        self.enable_docker_context = os.environ.get('DR_LOG_DOCKER', 'true').lower() == 'true'
        self.log_format = os.environ.get('DR_LOG_FORMAT', 'structured')  # 'structured' or 'simple'

    def _get_debug_level(self):
        level_str = os.environ.get('DRAGON_RUNNER_DEBUG', '1').upper()
        level_map = {'DEBUG': 0, 'INFO': 1, 'WARN': 2, 'ERROR': 3}
        return level_map.get(level_str, int(level_str) if level_str.isdigit() else 1)

    def _format_timestamp(self) -> str:
        return datetime.now().isoformat() if self.enable_timestamps else ""

    def _get_level_name(self, level: int) -> str:
        level_names = {0: "DEBUG", 1: "INFO", 2: "WARN", 3: "ERROR"}
        return level_names.get(level, "INFO")

    def log(self, level, indent, *args, **kwargs):
        if self.debug_level > level:
            return

        prefix = ' ' * indent
        level_name = self._get_level_name(level)

        if self.log_format == 'structured':
            timestamp = self._format_timestamp()
            if timestamp:
                prefix = f"[{timestamp}] [{level_name}] {prefix}"
            else:
                prefix = f"[{level_name}] {prefix}"

        print(prefix, *args, **kwargs)

    def debug(self, message: str, indent: int = 0, **kwargs):
        self.log(LogLevel.DEBUG.value, indent, message, **kwargs)

    def info(self, message: str, indent: int = 0, **kwargs):
        self.log(LogLevel.INFO.value, indent, message, **kwargs)

    def warn(self, message: str, indent: int = 0, **kwargs):
        self.log(LogLevel.WARN.value, indent, message, **kwargs)

    def error(self, message: str, indent: int = 0, **kwargs):
        self.log(LogLevel.ERROR.value, indent, message, **kwargs)

    def log_request(self, request_id: str, method: str, path: str, **context):
        """Log incoming HTTP requests with context"""
        self.info(f"Request {request_id}: {method} {path}", **context)

    def log_command(self, request_id: str, command: str, args: list, **context):
        """Log command execution attempts"""
        self.debug(f"Request {request_id}: Executing command: {command} {' '.join(args)}", **context)

    def log_command_result(self, request_id: str, command: str, exit_code: int,
                          stdout_size: int, stderr_size: int, execution_time: float, **context):
        """Log command execution results"""
        level = LogLevel.DEBUG.value if exit_code == 0 else LogLevel.WARN.value
        self.log(level, 0,
                f"Request {request_id}: Command '{command}' completed with exit code {exit_code}, "
                f"stdout: {stdout_size}B, stderr: {stderr_size}B, time: {execution_time:.4f}s", **context)

    def log_docker_context(self):
        """Log Docker environment information"""
        if not self.enable_docker_context:
            return

        self.info("=== Docker Environment Context ===")

        # Check if running in Docker
        if os.path.exists('/.dockerenv'):
            self.info("Running inside Docker container")
        else:
            self.info("Not running in Docker container")

        # Log key environment variables
        docker_vars = ['PATH', 'HOME', 'USER', 'DR_SERVER_MODE', 'DR_STATIC_DIR']
        for var in docker_vars:
            value = os.environ.get(var, '<not set>')
            self.debug(f"Environment: {var}={value}")

        # Log working directory
        try:
            cwd = os.getcwd()
            self.debug(f"Working directory: {cwd}")
        except Exception as e:
            self.warn(f"Could not get working directory: {e}")

    def log_executable_check(self, executable: str, exists: bool, accessible: bool, full_path: Optional[str]):
        """Log executable validation results"""
        if exists and accessible:
            self.debug(f"Executable check: {executable} -> {full_path} (OK)")
        elif exists and not accessible:
            self.warn(f"Executable check: {executable} -> {full_path} (EXISTS but NOT ACCESSIBLE)")
        else:
            self.error(f"Executable check: {executable} -> NOT FOUND")

class RequestContext:
    """Context manager for request-scoped logging with correlation IDs"""
    def __init__(self, method: str, path: str):
        self.request_id = str(uuid.uuid4())[:8]
        self.method = method
        self.path = path
        self.start_time = time.time()

    def __enter__(self):
        logger = get_logger()
        logger.log_request(self.request_id, self.method, self.path)
        return self.request_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logger = get_logger()
        if exc_type:
            logger.error(f"Request {self.request_id}: Failed after {duration:.4f}s: {exc_val}")
        else:
            logger.debug(f"Request {self.request_id}: Completed in {duration:.4f}s") 

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

def validate_docker_environment() -> Dict[str, Any]:
    """
    Validate Docker environment and return diagnostics
    """
    logger = get_logger()
    diagnostics = {
        "is_docker": os.path.exists('/.dockerenv'),
        "executables": {},
        "environment": {},
        "issues": []
    }

    # Check common executables
    common_exes = [
        '/usr/bin/generator',
        '/usr/bin/gcc',
        '/usr/bin/clang',
        '/bin/sh',
        '/bin/bash'
    ]

    for exe in common_exes:
        exists = os.path.exists(exe)
        accessible = exists and os.access(exe, os.X_OK)
        full_path = shutil.which(os.path.basename(exe)) if not exists else exe

        diagnostics["executables"][exe] = {
            "exists": exists,
            "accessible": accessible,
            "full_path": full_path
        }

        logger.log_executable_check(exe, exists, accessible, full_path)

        if not exists:
            diagnostics["issues"].append(f"Missing executable: {exe}")
        elif not accessible:
            diagnostics["issues"].append(f"Executable not accessible: {exe}")

    # Check environment variables
    important_vars = ['PATH', 'HOME', 'USER', 'DR_SERVER_MODE', 'DR_STATIC_DIR']
    for var in important_vars:
        diagnostics["environment"][var] = os.environ.get(var)

    return diagnostics

def create_request_context(method: str, path: str) -> RequestContext:
    """Helper function to create request context"""
    return RequestContext(method, path)
