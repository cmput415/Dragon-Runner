from typing     import List

class ConfigError:
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"CONFIG_ERROR: {self.message}"

class ErrorCollection:
    def __init__(self):
        self.errors: List[ConfigError] = []

    def add(self, error: ConfigError):
        self.errors.append(error)

    def extend(self, errors: List[ConfigError]):
        self.errors.extend(errors)

    def __bool__(self):
        return len(self.errors) > 0

    def __str__(self):
        return "\n".join(str(error) for error in self.errors)

class Verifiable:
    def verify(self) -> ErrorCollection:
        raise NotImplementedError("Subclasses must implement verify method")

