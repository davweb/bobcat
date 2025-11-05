"""Convert BBC Sounds subscription to an RSS Feed."""
# pylint: disable=broad-exception-caught

import os
import logging
import shutil
import sys
from pathlib import Path
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from . import audio
from . import bbc_sounds
from . import database
from . import download
from . import feed
from . import overcast
from . import s3sync
from .models import Episode
from .config import CONFIG


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
    # Workaround for yt-dlp not handling BBC Sounds URLs - https://github.com/yt-dlp/yt-dlp/issues/14569
    download_url = episode.url.replace('https://www.bbc.co.uk/sounds/play/', 'https://www.bbc.co.uk/programmes/')
    download.download_streaming_audio(download_url, episode.audio_filename)


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


def configure_logging() -> None:
    """Configure logging"""

    log_level = logging.getLevelName(CONFIG.log_level)

    if isinstance(log_level, str):
        raise ValueError(f'Invalid LOG_LEVEL: {CONFIG.log_level}')

    logging.basicConfig(encoding='utf-8',
                        filename=CONFIG.logfile,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='[%Y-%m-%dT%H:%M:%S%z]',
                        level=log_level)

    logging.debug('Starting')

    # Hide library logs
    library_log_level = logging.getLevelName(CONFIG.library_log_level)

    if isinstance(library_log_level, str):
        raise ValueError(f'Invalid LIBRARY_LOG_LEVEL: {CONFIG.library_log_level}')

    logging.getLogger('boto3').setLevel(library_log_level)
    logging.getLogger('botocore').setLevel(library_log_level)
    logging.getLogger('s3transfer').setLevel(library_log_level)
    logging.getLogger('urllib3').setLevel(library_log_level)
    logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(library_log_level)
    logging.getLogger('youtube-dl').setLevel(library_log_level)


def initialise_output_directory() -> None:
    """Initialise the working directory"""

    logging.debug('Output directory is %s', CONFIG.output_dir)

    Path(CONFIG.output_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(feed.LOGO_FILE, CONFIG.output_dir)
    os.chdir(CONFIG.output_dir)


def load_episode_metadata(episode: Episode) -> None:
    """Get metadata from website"""

    metadata = bbc_sounds.get_episode_metadata(episode.url)
    episode.title = metadata['title']
    episode.description = metadata['synopsis']
    episode.image_url = metadata['image_url']
    episode.published_utc = metadata['availability_from']
    logging.debug('Read metadata for episode %s from website', episode.episode_id)


def update_episode_list(session: Session) -> None:
    """Update the Episode database from the BBC Website"""

    logging.info('Fetching episode list')
    episode_urls = bbc_sounds.get_episode_urls()
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


def sync_episodes(session: Session) -> tuple[list[Episode], bool]:
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
    episodes = query.filter().order_by(Episode.published_utc.desc()).limit(CONFIG.max_episodes).all()
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

    configure_logging()
    logging.info('Episode limit is %d', CONFIG.max_episodes)

    with database.make_session() as session:

        if CONFIG.cache_only:
            logging.info('Generating feed using only cached data')
        else:
            update_episode_list(session)

        episodes, change = sync_episodes(session)

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
