import os
from io                     import BytesIO
from typing                 import Optional, Union
from dragon_runner.utils    import str_to_bytes, bytes_to_str
from dragon_runner.errors   import Verifiable, ErrorCollection, TestFileError

class TestFile(Verifiable):
    __test__ = False 
    def __init__(self, test_path, input_dir="input", input_stream_dir="input-stream",
                                  output_dir="output", comment_syntax="//"):   
        self.path = test_path
        self.stem, self.extension = os.path.splitext(os.path.basename(test_path))
        self.file = self.stem + self.extension  
        self.input_dir = input_dir
        self.input_stream_dir = input_stream_dir          
        self.output_dir = output_dir                
        self.comment_syntax = comment_syntax # default C99 //
        self.verify()
   
    def verify(self) -> ErrorCollection:
        """
        Ensure the paths supplied in CHECK_FILE and INPUT_FILE exist
        """
        collection = ErrorCollection()
        self.expected_out = self._get_content("CHECK:", "CHECK_FILE:")
        self.input_stream = self._get_content("INPUT:", "INPUT_FILE:")

        # If a parse and read of a tests input or output fails, propagate here 
        if isinstance(self.expected_out, TestFileError):
            collection.add(self.expected_out)
        if isinstance(self.input_stream, TestFileError):
            collection.add(self.input_stream) 
        if collection.has_errors():
            return collection

    def _get_content(self, inline_directive: str, file_directive: str) -> Union[bytes, TestFileError]:
        """
        Generic method to get content based on directives
        """
        content = self._get_directive_contents(inline_directive)
        if content:
            return content

        file_path = self._get_directive_contents(file_directive)
        if file_path:
            test_dir = os.path.dirname(self.path)
            full_path = os.path.join(test_dir, bytes_to_str(file_path))
            if not os.path.exists(full_path):
                return TestFileError(f"Failed to locate path supplied to {file_directive}: {full_path}")
            return self._get_file_bytes(full_path)
        
        return file_path  # default to empty content

    def _get_file_bytes(self, file_path: str) -> Optional[bytes]:
        """
        Get file contents in bytes
        """
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
                assert isinstance(file_bytes, bytes), "expected bytes"
                return file_bytes 
        except FileNotFoundError:
            return None

    def _get_directive_contents(self, directive_prefix: str) -> Union[bytes, TestFileError]:
        """
        Look into the testfile itself for contents defined in directives.
        Directives can appear anywhere in a line, as long as they're preceded by a comment syntax.
        """
        contents = BytesIO()
        first_match = True
        try:
            with open(self.path, 'r') as test_file:
                for line in test_file:
                    comment_index = line.find(self.comment_syntax)
                    directive_index = line.find(directive_prefix)
                    if comment_index == -1 or directive_index == -1 or comment_index > directive_index:
                        continue
                    
                    rhs_line = line.split(directive_prefix, 1)[1]
                    rhs_bytes = str_to_bytes(rhs_line, chop_newline=True)
                    if rhs_bytes is None:
                        return None
                    if not first_match:
                        contents.write(b'\n')

                    contents.write(rhs_bytes)                
                    first_match = False
            contents.seek(0)
            return contents.getvalue() if contents else None
        except UnicodeDecodeError as e:
            return TestFileError(e.reason)
        except Exception as e:
            return TestFileError(f"Unkown error occured while parsing testfile: {self.path}")

    def __repr__(self):
        max_test_name_length = 30
        test_name = os.path.basename(self.path)
        if len(test_name) > max_test_name_length:
            test_name = test_name[:max_test_name_length - 3] + "..."
        
        return (f"{test_name:<{max_test_name_length}}"
                f"{len(self.expected_out.getvalue()):>4}\t"
                f"{len(self.input_stream.getvalue()):>4}")
