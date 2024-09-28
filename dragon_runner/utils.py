import os
from typing     import Optional
from io         import BytesIO
from difflib    import Differ
from colorama   import Fore

def resolve_path(path) -> str:
    """
    return an absolute path given a relative or absolute path and
    empty string if the path does not exist (responsibility of user to verify)
    """
    try: 
        expanded_path = os.path.expanduser(path)    
        absolute_path = os.path.abspath(expanded_path) 
        return absolute_path
    except Exception:
        return ""

def precise_diff(produced: BytesIO, expected: BytesIO) -> str:
    """
    return the difference of two byte strings, otherwise empty string 
    """
    produced_str = produced.getvalue()
    expected_str = expected.getvalue()

    # if the strings are exactly the same produce no diff
    if produced_str == expected_str:
        return ""

    lines1 = produced_str.split(b'\n')
    lines2 = expected_str.split(b'\n')

    str_lines1 = [line.decode('utf-8') for line in lines1]
    str_lines2 = [line.decode('utf-8') for line in lines2]

    differ = Differ()
    diff = list(differ.compare(str_lines1, str_lines2))

    return '\n'.join(diff)

def lenient_diff(produced: BytesIO, expected: BytesIO, pattern: str) -> str:
    """
    check if the produced bytes are different from the expected bytes with
    respect to the regex pattern.
    """
    # TODO: implement the proper Error substring leniency 
    return precise_diff(produced, expected)

def get_test_result_string(diff) -> str:
    """
    Returns a colored string representation of the diff.
    """
    if not diff:
        return "No differences found."
    return Fore.RESET.join(Fore.GREEN + line if line.startswith('+') else 
                           Fore.RED + line if line.startswith('-') else 
                           line for line in diff) + Fore.RESET

