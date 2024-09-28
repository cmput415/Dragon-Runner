import os

def dump_file(file_path: str):    
    try:
        with open(file_path, 'r') as f:
            print(f.read())
    except:
        print("Unablbe to decode file: ", file_path)


def resolve_path(path):
    """
    return a absolute path given a relative or absolute path
    """
    expanded_path = os.path.expanduser(path)    
    absolute_path = os.path.abspath(expanded_path) 
    return absolute_path

