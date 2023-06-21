from typing import Self


class YoutubeDL(object):
    def __init__(self, options: dict) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def download(self, urls: list[str]) -> None: ...
