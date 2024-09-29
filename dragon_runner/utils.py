import os
import re
import tempfile
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

def make_tmp_file(content: BytesIO) -> str:
    """
    Create a file in tmp with the bytes from content
    """ 
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content.getvalue())
        return tmp.name

def str_to_bytes(string: str, chop_newline: bool=False) -> bytes:
 
    if chop_newline and string.endswith('\n'):
        string = string[:-1]

    bytes_io = BytesIO(string.encode('utf-8'))
    bytes_io.seek(0)
    return bytes_io.getvalue()

def bytes_to_str(bytes_io: BytesIO, encoding: str='utf-8') -> str: 
    bytes_io.seek(0)
    try:
        return bytes_io.getvalue().decode(encoding)
    except:
        return bytes_io.getvalue()