"""Database models"""

from datetime import timezone
from sqlalchemy import Column, DateTime, Integer, String
from bobcat.database import Base


class Episode(Base):
    """Single of episode of a show on BBC Sounds"""

    __tablename__ = 'episodes'
    episode_id = Column(String, primary_key=True)
    url = Column(String)
    title = Column(String)
    description = Column(String)
    image_url = Column(String)
    published_utc = Column('published', DateTime())
    size_in_bytes = Column(Integer)
    duration_in_seconds = Column(Integer)

    def __init__(self, url):
        self.url = url
        self.episode_id = url.split('/')[-1]

        self.title = None
        self.description = None
        self.image_url = None

    @property
    def audio_filename(self):
        """The filename for the downloaded audio file"""

        return f'{self.episode_id}.m4a'

    @property
    def output_filename(self):
        """The filename for the converted audio file to be uploaded"""
        return f'{self.episode_id}.mp3'

    @property
    def image_filename(self):
        """The filename for the episode image"""
        return f'{self.episode_id}.jpg'

    @property
    def published(self):
        """The publish date for this episode as a datetime with a timezone"""

        return self.published_utc.replace(tzinfo=timezone.utc)
