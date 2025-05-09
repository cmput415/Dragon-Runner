from typing import List, Union, Iterable

class Error:
    def __str__(self): raise NotImplementedError("Must implement __str__")

class ConfigError(Error):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"Config Error: {self.message}"

class TestFileError(Error):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"Testfile Error: {self.message}"

class ErrorCollection:
    def __init__(self, errors: Union[None, 'ErrorCollection', Iterable[Error]] = None):
        self.errors: List[Error] = []
        if errors is not None:
            if isinstance(errors, ErrorCollection):
                self.errors = errors.errors.copy()
            elif isinstance(errors, Iterable):
                self.errors = list(errors)

    def has_errors(self) -> bool:
        return self.__bool__()

    def add(self, error: Error):
        self.errors.append(error)

    def extend(self, errors: Union['ErrorCollection', Iterable[Error]]):
        if isinstance(errors, ErrorCollection):
            self.errors.extend(errors.errors)
        elif isinstance(errors, Iterable):
            self.errors.extend(errors)

    def __bool__(self):
        return len(self.errors) > 0

    def __eq__(self, other):
        if isinstance(other, bool):
            return bool(self) == other
        return False

    def __len__(self):
        return len(self.errors)

    def __str__(self):
        return "\n".join(str(error) for error in self.errors)

class Verifiable:
    def verify(self) -> ErrorCollection:
        raise NotImplementedError("Subclasses must implement verify method")

