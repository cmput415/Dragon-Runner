import os
from io import StringIO

class Test:
    def __init__(self, test_path):
        self.test_path              = test_path
        self.stem, self.extension   = os.path.splitext(os.path.basename(test_path))
        self.expected_out           = self.get_expected_out()
        self.input_stream           = self.get_input_stream()
    
    @staticmethod 
    def fill_stringio_from_file(file_path: str) -> StringIO:
        with open(file_path, 'r') as f:
            return StringIO(f.read())
         
    def fill_stringio_from_directive(self, file_suffix, directive_prefix, symmetric_dir) -> StringIO:
        """
        Generic method to get content either from a file or from directives in the test file.
        """
        # Case 1: Symmetric directory
        sym_path = self.test_path.replace("/input/", f"/{symmetric_dir}/")\
                                 .replace(self.extension, file_suffix)
        if os.path.exists(sym_path):
            return self.fill_stringio_from_file(sym_path)
             
        # Case 2: Same directory
        same_dir_path = self.test_path.replace(self.extension, file_suffix)
        if os.path.exists(same_dir_path):
            print("Found adjacent path: ", same_dir_path)
            return self.fill_stringio_from_file(same_dir_path)
       
        # Case 3: From directives in the test file
        content = []
        with open(self.test_path, 'r') as test_file:
            for line in test_file:
                if directive_prefix in line:
                    content.append(line.split(directive_prefix, 1)[1].strip())
        
        return StringIO('\n'.join(content))

    def get_expected_out(self) -> StringIO:
        return self.fill_stringio_from_directive(".out", "CHECK:", "output")

    def get_input_stream(self) -> StringIO:
        return self.fill_stringio_from_directive(".ins", "INPUT:", "input-stream")
    
    def __repr__(self):
        max_test_name_length = 30  # Adjust this value to change the maximum length of the test name
        test_name = os.path.basename(self.test_path)
        if len(test_name) > max_test_name_length:
            test_name = test_name[:max_test_name_length - 3] + "..."
        
        return (f"{test_name:<{max_test_name_length}}"
                f"{len(self.expected_out.getvalue()):>4}\t"
                f"{len(self.input_stream.getvalue()):>4}")

