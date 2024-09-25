import os
from io import StringIO, BytesIO
from typing import Optional, List

class Test:
    def __init__(self, test_path, input_dir="input",
                                  input_stream_dir="input-stream",
                                  output_dir="output",
                                  comment_syntax="//"):
        
        self.test_path              = test_path
        self.stem, self.extension   = os.path.splitext(os.path.basename(test_path))
       
        # default initialized
        self.input_dir              = input_dir
        self.input_stream_dir       = input_stream_dir
        self.output_dir             = output_dir
        self.comment_syntax         = comment_syntax
    
        # saturate byte streams 
        self.expected_out           = self.get_expected_out()
        self.input_stream           = self.get_input_stream()
 
    def get_file_bytes(self, file_path: str) -> BytesIO:
        with open(file_path, "rb") as f:
            return BytesIO(f.read())
    
    def get_directive_contents(self, directive_prefix: str) -> Optional[List[str]]:
        """
        Look into the testifle itself for contents defined in directives.
        """
        content = []
        with open(self.test_path, 'r') as test_file:
            for line in test_file:
                # TODO: assert comment syntax occurs before directive prefix
                if directive_prefix in line and line.startswith(self.comment_syntax):

                    content.append(line.split(directive_prefix, 1)[1].strip())
        return content if content is not [] else None 
    
    def get_file_contents(self, file_suffix, symmetric_dir) -> Optional[BytesIO]:
        """
        Look into a symetric directory and current directory for a file with an
        identical file path but differnt suffix.
        """
        sym_path = self.test_path.replace(self.input_dir, f"/{symmetric_dir}/")\
                                 .replace(self.extension, file_suffix)
        if os.path.exists(sym_path):
            return self.get_file_bytes(sym_path)
             
        same_dir_path = self.test_path.replace(self.extension, file_suffix)
        if os.path.exists(same_dir_path):
            return self.get_file_bytes(same_dir_path)
        
        return None

    def get_expected_out(self) -> BytesIO:
        """
        Load the expected output for a test into a byte stream
        """
        out_bytes = self.get_file_contents(".out", self.output_dir)
        if out_bytes:
            return out_bytes
        
        out_bytes = self.get_directive_contents("CHECK:")
        if out_bytes:
            return BytesIO("\n".join(out_bytes).encode('utf-8'))

        out_file = self.get_directive_contents("CHECK_FILE:")
        if out_file:
            test_dir = os.path.dirname(self.test_path)
            return self.get_file_bytes(os.path.join(test_dir, out_file[0]))
        
        # default expect empty output
        return BytesIO()
        
    def get_input_stream(self) -> BytesIO:
        """
        Load the input stream for a test into a byte stream
        """
        out_bytes = self.get_file_contents(".ins", self.input_stream_dir)
        if out_bytes:
            return out_bytes
        
        out_bytes = self.get_directive_contents("INPUT:")
        if out_bytes:
            return BytesIO("\n".join(out_bytes).encode('utf-8'))

        out_file = self.get_directive_contents("INPUT_FILE:")
        if out_file:
            test_dir = os.path.dirname(self.test_path)
            return self.get_file_bytes(os.path.join(test_dir, out_file[0]))
        
        # default empty input stream
        return BytesIO()
    
    def __repr__(self):
        max_test_name_length = 30
        test_name = os.path.basename(self.test_path)
        if len(test_name) > max_test_name_length:
            test_name = test_name[:max_test_name_length - 3] + "..."
        
        return (f"{test_name:<{max_test_name_length}}"
                f"{len(self.expected_out.getvalue()):>4}\t"
                f"{len(self.input_stream.getvalue()):>4}")

