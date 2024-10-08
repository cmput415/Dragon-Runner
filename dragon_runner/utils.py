import os
import sys
import tempfile
from typing     import Optional
from colorama   import init

# Initialize colorama
init(autoreset=True)

def resolve_relative_path(rel_path: str, dir: str) -> str:
    """
    Resolve relative path into an absolute path w.r.t dir.
    """
    if not os.path.isdir(dir):
        return ""
    return os.path.abspath(os.path.join(dir, rel_path))

def make_tmp_file(content: bytes) -> str:
    """
    Create a file in tmp with the bytes from content.
    """
    try: 
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            os.chmod(tmp.name, 0o700)
            return tmp.name
    except Exception as e:
        print(f"Failed to make temporary file with error: {e}", file=sys.stderr)

def str_to_bytes(string: str, chop_newline: bool=False) -> Optional[bytes]:
    """
    Convert a string to bytes. Optionally chop off the newline. Used for
    directive parsing.
    """
    if chop_newline and string.endswith('\n'):
        string = string[:-1]
    try:
        return string.encode('utf-8')
    except UnicodeEncodeError:
        return None

def bytes_to_str(data: bytes, encoding: str='utf-8') -> Optional[str]:
    """
    Convert bytes into a string.  
    """
    assert isinstance(data, bytes), "Supplied bytes that are not of type bytes."
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return str(data)
    except:
        return None

def file_to_bytes(file: str) -> Optional[bytes]:
    """
    Read a file in binary mode and return the bytes inside.
    Return None if an exception is thrown.
    """
    try:
        with open(file, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"Reading bytes from file failed with: {e}")
        return None

def file_to_str(file: str, max_bytes=1024) -> str:
    """
    return file in string form, with middle contents trucated if
    size exceeds max_bytes
    """ 
    file_bytes = file_to_bytes(file)
    if file_bytes is None:
        return ""
    
    if len(file_bytes) <= max_bytes:
        return bytes_to_str(file_bytes)
    
    half = (max_bytes - 3) // 2 
    truncated_bytes = file_bytes[:half] + \
        b'\n{{ Omitted middle bytes for brevity }}\n' + \
        file_bytes[-half:]
    
    return bytes_to_str(truncated_bytes)

def bytes_to_file(file: str, data: bytes) -> Optional[str]:
    """
    Write bytes directly into a file 
    """
    assert isinstance(data, bytes), "Supplied bytes that are not of type bytes."
    try:
        with open(file, 'w') as f:
            f.write(bytes_to_str(data))
            return file
    except Exception as e:
        print(f"Writting bytes to file failed with: {e}")
        return None