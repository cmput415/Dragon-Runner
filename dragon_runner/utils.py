def dump_file(file_path: str):    
    try:
        with open(file_path, 'r') as f:
            print(f.read())
    except:
        print("Unablbe to decode file: ", file_path)
