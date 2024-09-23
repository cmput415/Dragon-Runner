class ConfigError:
    def __init__(self, *errors):
        self.errors = list(errors)
   
    def add(self, error):
        if isinstance(error, ConfigError):
            self.errors.extend(error.errors)
        elif isinstance(error, str):
            self.errors.append(error)
        elif error is not None:
            raise TypeError("Can only add ConfigError, str, or None to ConfigError")
    
    def __bool__(self):
        return len(self.errors) > 0
    
    def __repr__(self):
        return "\n".join(self.errors)
    
    def __str__(self):
        return self.__repr__()
