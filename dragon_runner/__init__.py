try:
    from importlib.metadata import version
    __version__ = version("dragon-runner")
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import version
    __version__ = version("dragon-runner")
except Exception:
    # Fallback if package not installed
    __version__ = "1.0.0"