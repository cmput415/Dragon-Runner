import os

class Test:
    def __init__(self, test_path):
        self.test_path              = test_path
        self.stem, self.extension   = os.path.splitext(os.path.basename(test_path))
        self.expected_out           = self.get_expected_out()
        self.input_stream           = self.get_input_stream()
    
    @staticmethod 
    def get_file_contents(file):
        with open(file, 'r') as f:
            return f.read()

    def get_file_or_directive_content(self, file_suffix, directive_prefix, symmetric_dir):
        """
        Generic method to get content either from a file or from directives in the test file.
        """

        # Case 1: Symmetric directory
        sym_path = self.test_path.replace("/input/", f"/{symmetric_dir}/")\
                                 .replace(self.extension, file_suffix)
        if os.path.exists(sym_path):
            return self.get_file_contents(sym_path)
             
        # Case 2: Same directory
        same_dir_path = self.test_path.replace(self.extension, file_suffix)
        if os.path.exists(same_dir_path):
            return self.get_file_contents(same_dir_path)
       
        # Case 3: From directives in the test file
        test_contents = self.get_file_contents(self.test_path)
        content = []
        for line in test_contents.splitlines():
            if directive_prefix in line:
                content.append(line.split(directive_prefix, 1)[1].strip())
        
        return "\n".join(content) if content else ""

    def get_expected_out(self):
        return self.get_file_or_directive_content(".out", "CHECK:", "output")

    def get_input_stream(self): 
        return self.get_file_or_directive_content(".ins", "INPUT:", "input-stream")

    def __repr__(self):
        return (f"test='{os.path.basename(self.test_path)}'"
                f" expected_out_len={len(self.expected_out)}, "
                f" input_stream_len={len(self.input_stream)}")


