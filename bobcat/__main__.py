"""Convert BBC Sounds subscription to an RSS Feed."""

import argparse
import os
import logging
import shutil
from pathlib import Path
from datetime import timezone
from feedgen.feed import FeedGenerator
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from bobcat import audio
from bobcat import bbc_sounds
from bobcat import download
from bobcat import s3sync

RSS_FILE = 'podcast.xml'
LOGO_FILE = 'logo.png'

Base = declarative_base()

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


def download_episodes(episodes):
    """Download the assets for all episodes"""

    for episode in episodes:
        download_episode_audio(episode)
        download_episode_image(episode)
        convert_episode_audio(episode)


def download_episode_image(episode):
    """Download the image files for each episode"""

    if episode.is_image_downloaded():
        logging.debug('Image for episode %s already downloaded', episode.episode_id)
    else:
        logging.info('Downloading image for episode %s', episode.episode_id)
        download.download_file(episode.image_url, episode.image_filename)


def download_episode_audio(episode):
    """Download audio files for each episode"""

    if episode.is_audio_downloaded():
        logging.debug('Audio for episode %s already downloaded', episode.episode_id)
    else:
        logging.info('Downloading audio for episode %s', episode.episode_id)
        download.download_streaming_audio(episode.url, episode.audio_filename)


def convert_episode_audio(episode):
    """Convert the dowloaded mp4 file to mp3 and add cover art"""

    if episode.is_audio_converted():
        logging.debug('Audio for episode %s already converted', episode.episode_id)
        return

    logging.info('Coverting audio for episode %s', episode.episode_id)
    audio.convert_to_mp3(episode.audio_filename, episode.output_filename, episode.image_filename, episode.title)


def create_rss_feed(episodes, podcast_path):
    """Create the RSS file for the episodes"""
    logo_url = f'{podcast_path}/{LOGO_FILE}'

    episodes = [episode for episode in episodes if episode.is_audio_downloaded()]
    publication_date = max(episode.published() for episode in episodes)

    feed_generator = FeedGenerator()
    feed_generator.load_extension('podcast')

    feed_generator.title('BBC Sounds Subscriptions')
    feed_generator.description('Episodes of shows I have subscribed to on BBC Sounds')
    feed_generator.author({'name': 'BBC Sounds', 'email': 'RadioMusic.Support@bbc.co.uk'})
    feed_generator.logo(logo_url)
    feed_generator.link(href=f'{podcast_path}/{RSS_FILE}', rel='self')
    feed_generator.language('en')
    feed_generator.pubDate(publication_date)
    feed_generator.lastBuildDate(publication_date)

    feed_generator.podcast.itunes_category('Arts')
    feed_generator.podcast.itunes_category('Comedy')
    feed_generator.podcast.itunes_category('Music')
    feed_generator.podcast.itunes_category('News')
    feed_generator.podcast.itunes_category('Sports')
    feed_generator.podcast.itunes_author('BBC Sounds')
    feed_generator.podcast.itunes_block(True)
    feed_generator.podcast.itunes_explicit('no')
    feed_generator.podcast.itunes_image(logo_url)
    feed_generator.podcast.itunes_owner(name='BBC', email='RadioMusic.Support@bbc.co.uk')

    for episode in episodes:
        audio_url = f'{podcast_path}/{episode.output_filename}'
        image_url = f'{podcast_path}/{episode.image_filename}'

        feed_entry = feed_generator.add_entry()
        feed_entry.id(audio_url)
        feed_entry.title(episode.title)
        feed_entry.description(episode.description)
        feed_entry.enclosure(url=audio_url, length=str(episode.size_in_bytes()), type='audio/mpeg')
        feed_entry.published(episode.published())
        feed_entry.link(href=episode.url)
        feed_entry.podcast.itunes_duration(episode.duration_in_seconds())
        feed_entry.podcast.itunes_image(image_url)
        feed_entry.podcast.itunes_author('BBC Sounds')

    feed_generator.rss_file(RSS_FILE, pretty=True)


def upload_podcast(episodes, preview_mode):
    """Upload the podcast by syncing with an S3 bucket"""

    files_in_feed = set([RSS_FILE, LOGO_FILE])

    for episode in episodes:
        files_in_feed.add(episode.output_filename)
        files_in_feed.add(episode.image_filename)

    s3sync.files_with_bucket(files_in_feed, preview_mode)


def configure_logging(logfile):
    """Configure logging"""

    log_level_name = os.environ.get('LOG_LEVEL', 'INFO')
    log_level = logging.getLevelName(log_level_name)

    if isinstance(log_level, str):
        raise ValueError(f'Invalid LOG_LEVEL: {log_level_name}')

    logging.basicConfig(encoding='utf-8',
        filename=logfile,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='[%Y-%m-%dT%H:%M:%S%z]',
        level=log_level)

def main():
    """Main"""

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-o', '--output-dir', required=True, help='Output Directory')
    parser.add_argument('-e', '--no-episode-refresh', action='store_true',
        help='Generate feed using only cached episode data')
    parser.add_argument('-u', '--no-upload', action='store_true',
        help='Preview S3 changes without actually making them')
    parser.add_argument('-m', '--max-episodes', type=int, help='Maximum number of episodes')
    parser.add_argument('-l', '--logfile', type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir
    cache_only = args.no_episode_refresh
    preview_mode = args.no_upload
    logfile = args.logfile

    configure_logging(logfile)
    logging.info('Starting')
    logging.debug('Output directory is %s', output_dir)

    try:
        max_episodes = int(os.environ['EPISODE_LIMIT'])
        logging.debug('Episodes limit is %d', max_episodes)
    except (KeyError, ValueError):
        max_episodes = 20
        logging.info('Defaulting episode limit to %d', max_episodes)

    if cache_only:
        logging.info('Generating feed using only cached data')

    if preview_mode:
        logging.info('Showing changes to S3 but not making them')

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOGO_FILE, output_dir)
    os.chdir(output_dir)

    engine = create_engine('sqlite:///bobcat.db', echo=False)
    session_maker = sessionmaker(engine)
    Base.metadata.create_all(engine)

    with session_maker() as session:
        query = session.query(Episode)

        if not cache_only:
            logging.info('Fetching episode list')
            episode_urls = bbc_sounds.get_episode_urls(max_episodes)
            episodes = []
            new_episode_count = 0

            for url in episode_urls:
                episode = query.filter(Episode.url == url).one_or_none()

                if episode is None:
                    new_episode_count += 1
                    episode = Episode(url)
                    session.add(episode)

                episodes.append(episode)

            for episode in episodes:
                episode.load_metadata()

            session.commit()
            logging.info('Found %d new episodes', new_episode_count)

            # Clean up Selenium now to free memory in the container
            bbc_sounds.clean_up()

        episodes = query.filter().order_by(Episode.published_utc.desc()).limit(max_episodes).all()
        download_episodes(episodes)

        podcast_path = s3sync.bucket_url()
        create_rss_feed(episodes, podcast_path)
        upload_podcast(episodes, preview_mode)

    logging.info('Finished')

if __name__ == '__main__':
    main()
