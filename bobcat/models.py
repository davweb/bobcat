"""Database models"""

import logging
import os
from pathlib import Path
from datetime import timezone
from sqlalchemy import Column, String, DateTime
from bobcat import audio
from bobcat import bbc_sounds
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

    def published(self):
        """The publish date for this episode as a datetime with a timezone"""

        return self.published_utc.replace(tzinfo=timezone.utc)

    def size_in_bytes(self):
        """The size in bytes of the output audio file"""

        return os.path.getsize(self.output_filename)

    def duration_in_seconds(self):
        """Returns the duration in seconds of the output file as an int"""

        return audio.duration_in_seconds(self.output_filename)


    def is_audio_downloaded(self):
        """Returns true if the audio is downloaded for this episode"""

        return Path(self.audio_filename).exists()


    def is_image_downloaded(self):
        """Returns true if the audio is downloaded for this episode"""

        return Path(self.image_filename).exists()


    def is_audio_converted(self):
        """Returns true if the audio has been converted for this episode"""

        return Path(self.output_filename).exists()


    def load_metadata(self):
        """Get metadata from local cache or from website"""

        if self.title is None or self.description is None or self.image_url is None:
            metadata = bbc_sounds.get_episode_metadata(self.url)
            self.title = metadata['title']
            self.description = metadata['synopsis']
            self.image_url = metadata['image_url']
            self.published_utc = metadata['availability_from']
            logging.debug('Read metadata for episode %s from website', self.episode_id)
