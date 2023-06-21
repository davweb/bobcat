"""Convert BBC Sounds subscription to an RSS Feed."""
# pylint: disable=broad-exception-caught

import argparse
import os
import logging
import shutil
import sys
from pathlib import Path
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from bobcat import audio
from bobcat import bbc_sounds
from bobcat import database
from bobcat import download
from bobcat import feed
from bobcat import overcast
from bobcat import s3sync
from bobcat.models import Episode


def download_episodes(episodes: list[Episode]) -> None:
    """Download the assets for all episodes"""

    for episode in episodes:
        download_episode(episode)


def download_episode(episode: Episode) -> None:
    """Download all the assets for the episode"""

    download_episode_image(episode)
    download_episode_audio(episode)
    convert_episode_audio(episode)
    episode.size_in_bytes = os.path.getsize(episode.output_filename)
    episode.duration_in_seconds = audio.duration_in_seconds(episode.output_filename)


def download_episode_image(episode: Episode) -> None:
    """Download the image files for each episode"""

    if Path(episode.image_filename).exists():
        logging.debug('Image for episode %s already downloaded', episode.episode_id)
        return

    logging.info('Downloading image for episode %s - "%s"', episode.episode_id, episode.title)
    download.download_file(episode.image_url, episode.image_filename)


def download_episode_audio(episode: Episode) -> None:
    """Download audio files for each episode"""

    if Path(episode.audio_filename).exists():
        logging.debug('Audio for episode %s already downloaded', episode.episode_id)
        return

    logging.info('Downloading audio for episode %s - "%s"', episode.episode_id, episode.title)
    download.download_streaming_audio(episode.url, episode.audio_filename)


def convert_episode_audio(episode: Episode) -> None:
    """Convert the downloaded mp4 file to mp3 and add cover art"""

    if Path(episode.output_filename).exists():
        logging.debug('Audio for episode %s already converted', episode.episode_id)
        return

    logging.info('Converting audio for episode %s - "%s"', episode.episode_id, episode.title)
    audio.convert_to_mp3(
        episode.audio_filename,
        episode.output_filename,
        episode.image_filename,
        episode.title)


def configure_logging(logfile: str) -> None:
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
    library_log_level_name = os.environ.get('LIBRARY_LOG_LEVEL', 'CRITICAL')
    library_log_level = logging.getLevelName(library_log_level_name)

    logging.getLogger('boto3').setLevel(library_log_level)
    logging.getLogger('botocore').setLevel(library_log_level)
    logging.getLogger('s3transfer').setLevel(library_log_level)
    logging.getLogger('urllib3').setLevel(library_log_level)
    logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(library_log_level)
    logging.getLogger('youtube-dl').setLevel(library_log_level)


def initialise_output_directory(output_dir: str) -> None:
    """Initialise the working directory"""

    logging.debug('Output directory is %s', output_dir)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(feed.LOGO_FILE, output_dir)
    os.chdir(output_dir)


def process_configuration() -> tuple[bool, int]:
    """Configuration from command line arguments and environment variables"""

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-o', '--output-dir', required=True, help='Output Directory')
    parser.add_argument('-n', '--no-episode-refresh', action='store_true',
                        help='Generate feed using only cached episode data')
    parser.add_argument('-l', '--logfile', type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir
    cache_only = args.no_episode_refresh
    logfile = args.logfile

    configure_logging(logfile)
    logging.debug('Starting')
    initialise_output_directory(output_dir)

    try:
        max_episodes = int(os.environ['EPISODE_LIMIT'])
        logging.debug('Episodes limit is %d', max_episodes)
    except (KeyError, ValueError):
        max_episodes = 20
        logging.info('Defaulting episode limit to %d', max_episodes)

    if cache_only:
        logging.info('Generating feed using only cached data')

    return (cache_only, max_episodes)


def load_episode_metadata(episode: Episode) -> None:
    """Get metadata from website"""

    metadata = bbc_sounds.get_episode_metadata(episode.url)
    episode.title = metadata['title']
    episode.description = metadata['synopsis']
    episode.image_url = metadata['image_url']
    episode.published_utc = metadata['availability_from']
    logging.debug('Read metadata for episode %s from website', episode.episode_id)


def update_episode_list(session: Session, max_episodes: int) -> None:
    """Update the Episode database from the BBC Website"""

    logging.info('Fetching episode list')
    episode_urls = bbc_sounds.get_episode_urls(max_episodes)
    episodes = []
    new_episode_count = 0
    query = session.query(Episode)

    for url in episode_urls:
        episode = query.filter(Episode.url == url).one_or_none()

        if episode is None:
            new_episode_count += 1
            episode = Episode(url)
            session.add(episode)

        episodes.append(episode)

    for episode in episodes:
        if episode.title is None or episode.description is None or episode.image_url is None:
            load_episode_metadata(episode)

    session.commit()
    logging.info('Found %d new episodes', new_episode_count)

    # Clean up Selenium now to free memory in the container
    bbc_sounds.clean_up()


def get_bucket_contents() -> set[str]:
    """Get S3 Bucket contents, exiting with error on failure"""

    try:
        return s3sync.get_bucket_contents()
    except ClientError as client_error:
        error = client_error.response.get('Error', {}).get('Code', None)

        if error == 'SignatureDoesNotMatch':
            logging.error('AWS Authorization failure. Are the AWS credentials correct?')
        elif error == 'AccessDenied':
            logging.error(
                'Access denied to S3 bucket. Does the account have the correct permissions?')
        elif error == 'NoSuchBucket':
            logging.error('Unknown S3 bucket. Is the bucket name correct?')
        elif error is not None:
            logging.error('Failed to query S3 bucket due to %s error.', error)
        else:
            logging.error('Failed to query S3 bucket.', exc_info=client_error)

        sys.exit(1)
    except Exception as exception:
        logging.error('Failed to query S3 bucket.', exc_info=exception)
        sys.exit(1)


def sync_episodes(session: Session, max_episodes: int) -> tuple[list[Episode], bool]:
    """Download episode audio and upload it to S3"""

    bucket_contents = get_bucket_contents()
    change = False

    # handle logo - ignore it if it's there, upload it if it's not
    if feed.LOGO_FILE in bucket_contents:
        bucket_contents.remove(feed.LOGO_FILE)
    else:
        s3sync.upload_file(feed.LOGO_FILE)
        change = True

    # Ignore feed file for now
    bucket_contents.remove(feed.RSS_FILE)

    query = session.query(Episode)
    episodes = query.filter().order_by(Episode.published_utc.desc()).limit(max_episodes).all()
    uploaded_episodes = []

    for episode in episodes:
        episode_files = set([episode.output_filename, episode.image_filename])
        episode_uploaded = episode_files.issubset(bucket_contents)
        bucket_contents -= episode_files

        if episode_uploaded:
            logging.debug('Episode %s already in S3 Bucket', episode.episode_id)
            uploaded_episodes.append(episode)
            continue

        try:
            download_episode(episode)
            session.commit()
            s3sync.upload_files(episode_files)
        except Exception as exception:
            logging.warning(
                'Failed to sync episode %s - "%s"',
                episode.episode_id,
                episode.title,
                exc_info=exception)
            continue

        uploaded_episodes.append(episode)
        change = True

        try:
            for filename in episode_files:
                os.remove(filename)
                logging.debug('Deleted %s', filename)
        except Exception as exception:
            logging.warning('Failed to delete files for episode %s - "%s"',
                            episode.episode_id, episode.title, exc_info=exception)

    #  Delete old files in the S3 bucket
    if bucket_contents:
        change = True

        try:
            s3sync.delete_files(bucket_contents)
        except Exception as exception:
            logging.warning('Failed to tidy S3 bucket', exc_info=exception)

    return uploaded_episodes, change


def main() -> None:
    """Main"""

    (cache_only, max_episodes) = process_configuration()

    with database.make_session() as session:

        if not cache_only:
            update_episode_list(session, max_episodes)

        episodes, change = sync_episodes(session, max_episodes)

        if change:
            podcast_path = s3sync.bucket_url()
            feed.create_rss_feed(episodes, podcast_path)
            s3sync.upload_file(feed.RSS_FILE)
            podcast_url = f'{podcast_path}/{feed.RSS_FILE}'
            overcast.ping(podcast_url)
            logging.info('Finished. Podcast feed available at %s', podcast_url)
        else:
            logging.info('Finished with no changes')


if __name__ == '__main__':
    main()
