"""Database models"""

from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import mapped_column
from bobcat.database import Base


class Episode(Base):
    """Single of episode of a show on BBC Sounds"""

    __tablename__ = 'episodes'
    episode_id = mapped_column(String, primary_key=True)
    url = mapped_column(String)
    title = mapped_column(String)
    description = mapped_column(String)
    image_url = mapped_column(String)
    published_utc = mapped_column('published', DateTime())
    size_in_bytes = mapped_column(Integer)
    duration_in_seconds = mapped_column(Integer)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.episode_id = url.split('/')[-1]

        self.title = None
        self.description = None
        self.image_url = None

    @property
    def audio_filename(self) -> str:
        """The filename for the downloaded audio file"""

        return f'{self.episode_id}.m4a'

    @property
    def output_filename(self) -> str:
        """The filename for the converted audio file to be uploaded"""
        return f'{self.episode_id}.mp3'

    @property
    def image_filename(self) -> str:
        """The filename for the episode image"""
        return f'{self.episode_id}.jpg'

    @property
    def published(self) -> datetime:
        """The publish date for this episode as a datetime with a timezone"""

        return self.published_utc.replace(tzinfo=timezone.utc)
