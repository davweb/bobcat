from abc import ABCMeta

class BaseOptions(metaclass=ABCMeta):
    pass

class ArgOptions(BaseOptions):
    def __init__(self) -> None: ...
    def add_argument(self, argument: str) -> None: ...
