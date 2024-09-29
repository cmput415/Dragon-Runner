import os
import re
from typing     import Optional, Tuple
from io         import BytesIO
from difflib    import Differ
from colorama   import Fore, init

# Initialize colorama
init(autoreset=True)

def resolve_relative_path(rel_path: str, dir: str) -> str:
    """
    Resolve relative path into an absolute path w.r.t dir
    """
    if not os.path.isdir(dir):
        return ""
    return os.path.abspath(os.path.join(dir, rel_path))
