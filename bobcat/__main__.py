"""Convert BBC Sounds subscription to an RSS Feed."""

import argparse
import os
import logging
import shutil
from pathlib import Path
from bobcat import audio
from bobcat import bbc_sounds
from bobcat import database
from bobcat import download
from bobcat import feed
from bobcat import s3sync
from bobcat.models import Episode


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
        logging.info('Downloading image for episode %s - "%s"', episode.episode_id, episode.title)
        download.download_file(episode.image_url, episode.image_filename)


def download_episode_audio(episode):
    """Download audio files for each episode"""

    if episode.is_audio_downloaded():
        logging.debug('Audio for episode %s already downloaded', episode.episode_id)
    else:
        logging.info('Downloading audio for episode %s - "%s"', episode.episode_id, episode.title)
        download.download_streaming_audio(episode.url, episode.audio_filename)


def convert_episode_audio(episode):
    """Convert the dowloaded mp4 file to mp3 and add cover art"""

    if episode.is_audio_converted():
        logging.debug('Audio for episode %s already converted', episode.episode_id)
        return

    logging.info('Coverting audio for episode %s - "%s"', episode.episode_id, episode.title)
    audio.convert_to_mp3(episode.audio_filename, episode.output_filename, episode.image_filename, episode.title)


def upload_podcast(episodes, preview_mode):
    """Upload the podcast by syncing with an S3 bucket"""

    files_in_feed = set([feed.RSS_FILE, feed.LOGO_FILE])

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

    # Hide library logs
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('s3transfer').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)



def process_configuration():
    """Configuration from command line arguments and environment variables"""

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
    logging.debug('Starting')
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

    return (output_dir, cache_only, preview_mode, max_episodes)


def main():
    """Main"""

    (output_dir, cache_only, preview_mode, max_episodes) = process_configuration()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(feed.LOGO_FILE, output_dir)
    os.chdir(output_dir)

    with database.make_session() as session:
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
        feed.create_rss_feed(episodes, podcast_path)
        upload_podcast(episodes, preview_mode)

    logging.info('Finished. Podcast feed available at %s/%s', podcast_path, feed.RSS_FILE)

if __name__ == '__main__':
    main()
