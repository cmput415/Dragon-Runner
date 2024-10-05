import os
import io
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
        os.chmod(tmp.name, 0o700)
        return tmp.name

def str_to_bytes(string: str, chop_newline: bool=False) -> bytes:
 
    if chop_newline and string.endswith('\n'):
        string = string[:-1]

    bytes_io = BytesIO(string.encode('utf-8'))
    bytes_io.seek(0)
    return bytes_io.getvalue()

def bytes_to_str(data, encoding: str='utf-8') -> str:
    if isinstance(data, BytesIO):
        data.seek(0)
        data = data.getvalue()
    try:
        return data.decode(encoding)
    except:
        return str(data)

def file_to_bytes(file: str) -> Optional[BytesIO]:
    try:
        with open(file, 'rb') as f:
            return BytesIO(f.read())
    except Exception as e:
        print(f"Reading bytes from file failed with: {e}")
        return None

def file_to_str(file: str, max_bytes=1024) -> str:
    """
    return file in string form, with middle contents trucated if
    size exceeds max_bytes
    """ 
    bytes_io = file_to_bytes(file)
    if bytes_io is None:
        return ""
    
    bytes_data = bytes_io.getvalue()
    if len(bytes_data) <= max_bytes:
        return bytes_to_str(bytes_data)
    
    half = (max_bytes - 3) // 2 
    truncated_bytes = bytes_data[:half] + b'...' + bytes_data[-half:]
    return bytes_to_str(truncated_bytes)

def bytes_to_file(file: str, bytes: BytesIO) -> Optional[str]:
    try:
        with open(file, 'w') as f:
            f.write(bytes_to_str(bytes))
            return file
    except Exception as e:
        print(f"Writting bytes to file failed with: {e}")
        return None