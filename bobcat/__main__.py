"""Convert BBC Sounds subscription to an RSS Feed."""

import argparse
import os
import logging
import json
import shutil
from pathlib import Path
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
from bobcat import audio
from bobcat import bbc_sounds
from bobcat import download
from bobcat import s3sync

RSS_FILE = 'podcast.xml'
LOGO_FILE = 'logo.png'


class Episode:
    """Single of episode of a show on BBC Sounds"""

    def __init__(self, url=None, episode_id=None):
        if episode_id:
            self.episode_id = episode_id
        else:
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
    def metadata_filename(self):
        """The filename for metadata file"""
        return f'{self.episode_id}.json'

    @property
    def image_filename(self):
        """The filename for the episode image"""
        return f'{self.episode_id}.jpg'

    def published(self):
        """The publish date for this episode as a datetime

        The publish date is currently calculated as the last modified time of
        the downloaded audio file.
        """

        mtime = os.path.getmtime(self.audio_filename)
        # TODO check Timezone
        return datetime.fromtimestamp(mtime, pytz.utc)

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


    def _read_metadata_file(self):
        with open(self.metadata_filename, encoding='utf8') as metadata:
            episode_metadata = json.loads(metadata.read())

        if episode_metadata['id'] != self.episode_id:
            raise ValueError()

        self.url = episode_metadata['url']
        self.title = episode_metadata['title']
        self.description = episode_metadata['description']
        self.image_url = episode_metadata['image_url']


    def _write_metadata_file(self):
        episode_metadata = {
            'id': self.episode_id,
            'url': self.url,
            'title': self.title,
            'description': self.description,
            'image_url': self.image_url
        }

        with open(self.metadata_filename, mode='w', encoding='utf8') as metadata:
            metadata.write(json.dumps(episode_metadata))


    def load_metadata(self):
        """Get metadata from local cache or from website"""

        try:
            self._read_metadata_file()
            logging.info('Read metadata for %s from file %s', self.episode_id, self.metadata_filename)
        except:
            self._fetch_metadata()
            self._write_metadata_file()
            logging.info('Read metadata for episode %s from website', self.episode_id)


    def _fetch_metadata(self):
        """Get information about an episode from the BBC Sounds website"""

        metadata = bbc_sounds.get_episode_metadata(self.url)

        self.title = metadata['title']
        self.description = metadata['description']
        self.image_url = metadata['image_url']


def download_episodes(episodes):
    """Download the assets for all episodes"""

    for episode in episodes:
        download_episode_audio(episode)
        download_episode_image(episode)
        convert_episode_audio(episode)


def download_episode_image(episode):
    """Download the image files for each episode"""

    if episode.is_image_downloaded():
        logging.info('Image for episode %s already downloaded', episode.episode_id)
    else:
        download.download_file(episode.image_url, episode.image_filename)


def download_episode_audio(episode):
    """Download audio files for each episode"""

    if episode.is_audio_downloaded():
        logging.info('Audio for episode %s already downloaded', episode.episode_id)
    else:
        download.download_streaming_audio(episode.url, episode.audio_filename)


def convert_episode_audio(episode):
    """Convert the dowloaded mp4 file to mp3 and add cover art"""

    if episode.is_audio_converted():
        logging.info('Audio for episode %s already converted', episode.episode_id)
        return

    audio.convert_to_mp3(episode.audio_filename, episode.output_filename, episode.image_filename, episode.title)


def load_episodes():
    """Create episodes from local data rather than the BBC Sounds website"""

    episodes = []

    for file in os.listdir('.'):
        if file.endswith('.json'):
            episode_id = file[:-5]
            episode = Episode(episode_id=episode_id)
            episode.load_metadata()
            episodes.append(episode)

    return episodes


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


def upload_podcast(episodes, aws_access_id, aws_secret_key, s3_bucket_name):
    """Upload the podcast by syncing with an S3 bucket"""

    files_in_feed = set([RSS_FILE, LOGO_FILE])

    for episode in episodes:
        files_in_feed.add(episode.output_filename)
        files_in_feed.add(episode.image_filename)

    s3sync.files_with_bucket(aws_access_id, aws_secret_key, s3_bucket_name, files_in_feed)


def main():
    """Main"""

    logging.basicConfig(encoding='utf-8',
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO)

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-o', '--output-dir', required=True, help='Output Directory')
    parser.add_argument('-c', '--cache', action='store_true', help='Generate feed using cached data')
    parser.add_argument('-m', '--max-episodes', type=int, help='Maximum number of episodes')
    parser.add_argument('-a', '--aws-access-id', required=True, help='AWS Access Key ID')
    parser.add_argument('-k', '--aws-secret-key', required=True, help='AWS Secret Key')
    parser.add_argument('-b', '--aws-bucket', required=True, help='AWS S3 Bucket Name')
    args = parser.parse_args()
    output_dir = args.output_dir
    cache = args.cache
    max_episodes = args.max_episodes
    aws_access_id = args.aws_access_id
    aws_secret_key = args.aws_secret_key
    aws_bucket_name = args.aws_bucket

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOGO_FILE, output_dir)
    os.chdir(output_dir)

    if cache:
        episodes = load_episodes()
    else:
        episode_urls = bbc_sounds.get_episode_urls(max_episodes)
        episodes = [Episode(url) for url in episode_urls]

        for episode in episodes:
            episode.load_metadata()

        download_episodes(episodes)

    podcast_path = s3sync.bucket_url(aws_bucket_name)
    create_rss_feed(episodes, podcast_path)
    upload_podcast(episodes, aws_access_id, aws_secret_key, aws_bucket_name)


if __name__ == '__main__':
    main()
