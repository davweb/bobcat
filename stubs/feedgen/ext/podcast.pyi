class PodcastExtension:
    def itunes_category(self, category: str) -> None: ...
    def itunes_author(self, author: str) -> None: ...
    def itunes_block(self, block: bool) -> None: ...
    def itunes_explicit(self, explict: str) -> None: ...
    def itunes_image(self, image_url: str) -> None: ...
    def itunes_duration(self, duration: int) -> None: ...