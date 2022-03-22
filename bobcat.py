"""Convert BBC Sounds subscription to an RSS Feed."""

import argparse
import os

import json
import shutil
from pathlib import Path
from datetime import datetime
import boto3
import pydub
import pytz
import requests
import youtube_dl
from feedgen.feed import FeedGenerator
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


URL_BBC_LOGIN = 'https://account.bbc.com/signin'
URL_BBC_SOUNDS = 'https://www.bbc.co.uk/sounds'
URL_BBC_MY_SOUNDS = 'https://www.bbc.co.uk/sounds/my?page={}'

RSS_FILE = 'podcast.xml'
LOGO_FILE = 'logo.png'

DRIVER = None

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
        self.duration_in_seconds = None

    def __getattr__(self, attribute):
        if attribute == 'audio_filename':
            return f'{self.episode_id}.m4a'

        if attribute == 'output_filename':
            return f'{self.episode_id}.mp3'

        if attribute == 'metadata_filename':
            return f'{self.episode_id}.json'

        if attribute == 'image_filename':
            return f'{self.episode_id}.jpg'

        if attribute == 'published':
            mtime = os.path.getmtime(self.audio_filename)
            # TODO check Timezone
            return datetime.fromtimestamp(mtime, pytz.utc)

        if attribute == 'size_in_bytes':
            return os.path.getsize(self.output_filename)

        raise AttributeError

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
            print(f'Read metadata for {self.episode_id} from file {self.metadata_filename}')
        except:
            self._fetch_metadata()
            self._write_metadata_file()
            print(f'Read metadata for {self.episode_id} from website')


    def _fetch_metadata(self):
        """Get information about an episode from the BBC Sounds website"""

        DRIVER.get(self.url)

        try:
            show_more = DRIVER.find_element(By.CLASS_NAME, 'sc-c-synopsis__button')
            show_more.click()
        except NoSuchElementException:
            pass

        heading = DRIVER.find_element(By.CSS_SELECTOR, '.sc-c-herospace__details-titles .sc-u-screenreader-only')
        synopsis = DRIVER.find_element(By.CLASS_NAME, 'sc-c-synopsis')
        image = DRIVER.find_element(By.CLASS_NAME, 'sc-c-herospace__image')

        title = heading.text

        if title.endswith(' - BBC Sounds'):
            title = title[:-13]

        description = synopsis.text

        if description.endswith(' Read less'):
            description = description[:-10]

        # TODO move this elsewhere and hunt for images
        # Get a better quality image if possible
        img_url = image.get_attribute('src')
        img_url = img_url.replace('320x320', '1600x1600')

        self.title = title
        self.description = description
        self.image_url = img_url


def initialise_selenium(foreground):
    """Initialise the Selenium driver"""
    chrome_options = Options()

    if foreground:
        chrome_options.add_experimental_option('detach', True)
    else:
        chrome_options.add_argument('--headless')

    chromedriver_path = os.path.join((os.path.dirname(os.path.realpath(__file__))), 'chromedriver')
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1024, 1280)
    return driver


def clean_up_selenium():
    """Tidy up Selenium resources"""
    DRIVER.close()


def bbc_login(bbc_username, bbc_password):
    """Login in to the BBC site"""

    DRIVER.get(URL_BBC_LOGIN)
    username_field = DRIVER.find_element(By.ID, 'user-identifier-input')
    username_field.send_keys(bbc_username)
    password_field = DRIVER.find_element(By.ID, 'password-input')
    password_field.send_keys(bbc_password)
    submit_button = DRIVER.find_element(By.ID, 'submit-button')
    submit_button.click()


def accept_cookie_prompt():
    """Click on the accept cookies prompt"""

    DRIVER.get(URL_BBC_SOUNDS)
    accept_cookies = DRIVER.find_elements(By.CSS_SELECTOR, '#bbccookies-continue-button')
    accept_cookies[0].click()


def get_episodes(max_episodes):
    """Get the episodes of shows subscribed to on BBC Sounds"""

    episode_urls = []
    page = 0

    while True:
        page += 1
        DRIVER.get(URL_BBC_MY_SOUNDS.format(page))
        locations = DRIVER.find_elements(By.CSS_SELECTOR, 'div.sounds-react-app li a[href*="/play/"]')
        page_episode_urls = [anchor.get_attribute('href') for anchor in locations]
        episode_count = len(page_episode_urls)

        if episode_count == 0:
            break

        print(f'Found {episode_count} episodes on page {page}')
        episode_urls += page_episode_urls

        if len(episode_urls) >= max_episodes:
            episode_urls = episode_urls[:max_episodes]
            break


    episodes  = [Episode(url) for url in episode_urls]

    for episode in episodes:
        episode.load_metadata()

    return episodes


def download_episodes(episodes):
    """Download the assets for all episodes"""

    for episode in episodes:
        download_episode_audio(episode)
        download_episode_image(episode)
        convert_episode_audio(episode)


def download_episode_image(episode):
    """Download the image files for each episode"""

    if episode.is_image_downloaded():
        print(f'Image for episode {episode.episode_id} already downloaded')
    else:
        response = requests.get(episode.image_url, stream=True)
        with open(episode.image_filename, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)

        print(f'Image for episode {episode.episode_id} downloaded from website')


def download_episode_audio(episode):
    """Download audio files for each episode"""

    if episode.is_audio_downloaded():
        print(f'Audio for episode {episode.episode_id} already downloaded')
    else:
        ydl_options = {
            'outtmpl': episode.audio_filename,
            'format': 'bestaudio[ext=m4a]'
        }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:

            try:
                # This automatically skips if file is already downloaded
                ydl.download([episode.url])
            except:
                pass


def convert_episode_audio(episode):
    """Convert the dowloaded mp4 file to mp3 and add cover art"""

    audio = pydub.AudioSegment.from_file(episode.audio_filename)
    episode.duration_in_seconds = int(audio.duration_seconds)

    if episode.is_audio_converted():
        print(f'Audio for episode {episode.episode_id} already converted')
        return

    tags={'title': episode.title}

    # disable writing encoding information as it's wrong and says VBR instead of CBR 
    parameters = ['-write_xing','0']

    audio.export(episode.output_filename, format='mp3', bitrate='128k', tags=tags, cover=episode.image_filename, parameters=parameters)
    print(f'Converted audio for episode {episode.episode_id}')


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

    episodes = (episode for episode in episodes if episode.is_audio_downloaded())

    feed_generator = FeedGenerator()
    feed_generator.load_extension('podcast')

    feed_generator.title('BBC Sounds Subscriptions')
    feed_generator.description('Episodes of shows I have subscribed to on BBC Sounds')
    feed_generator.author({'name': 'BBC Sounds', 'email': 'sounds@bbc.co.uk'})
    feed_generator.logo(logo_url)
    feed_generator.link(href=URL_BBC_SOUNDS, rel='alternate')
    feed_generator.link(href=f'{podcast_path}/{RSS_FILE}', rel='self')
    feed_generator.language('en')

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
        feed_entry.enclosure(url=audio_url, length=str(episode.size_in_bytes), type='audio/mpeg')
        feed_entry.published(episode.published)
        feed_entry.link(href=episode.url)
        feed_entry.podcast.itunes_duration(episode.duration_in_seconds)
        feed_entry.podcast.itunes_image(image_url)
        feed_entry.podcast.itunes_author('BBC Sounds')

    feed_generator.rss_str(pretty=True)
    feed_generator.rss_file(RSS_FILE)


def get_content_type(filename):
    """Determine the mime type of each file to be uploaded to S3 by its extension."""

    if filename.endswith('.xml'):
        return 'application/rss+xml'

    if filename.endswith('.mp3'):
        return 'audio/mpeg'

    if filename.endswith('.jpg'):
        return 'image/jpeg'

    if filename.endswith('.png'):
        return 'image/png'

    raise ValueError(f'Could not determine content type for file "{filename}"')


def sync_with_s3(episodes, aws_access_id, aws_secret_key, s3_bucket_name):
    """Upload new and updated files to s3 and delete old ones"""

    s3_client = boto3.resource('s3', aws_access_key_id=aws_access_id, aws_secret_access_key=aws_secret_key)
    bucket = s3_client.Bucket(s3_bucket_name)
    uploaded = set(object.key for object in bucket.objects.all())

    in_feed = set([RSS_FILE, LOGO_FILE])

    for episode in episodes:
        in_feed.add(episode.output_filename)
        in_feed.add(episode.image_filename)

    to_upload = in_feed - uploaded
    to_delete = uploaded - in_feed

    # Always upload the latest RSS file
    to_upload.add(RSS_FILE)

    print(f'Uploading {len(to_upload)} files to S3 Bucket {s3_bucket_name}')

    for file in to_upload:
        bucket.upload_file(file, file,
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': get_content_type(file)
            }
        )
        # s3_object = s3_client.Bucket(s3_bucket_name).Object(file)
        # s3_object.Acl().put(ACL='public-read')
        print (f'Uploaded {file} to S3 Bucket {s3_bucket_name}')

    if to_delete:
        objects_to_delete = [{'Key': file} for file in to_delete]
        bucket.delete_objects(Delete={'Objects': objects_to_delete})
        print (f'Removed {",".join(to_delete)} from S3 Bucket {s3_bucket_name}')


def main():
    """Main"""

    global DRIVER

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-u', '--bbc-username', required=True, help='BBC account username or email')
    parser.add_argument('-p', '--bbc-password', required=True, help='BBC account password')
    parser.add_argument('-s', '--show-browser', action='store_true', help='Show automation browser in the foreground')
    parser.add_argument('-o', '--output-dir', required=True, help='Output Directory')
    parser.add_argument('-x', '--podcast-path', required=True, help='Podcast Path Prefix')
    parser.add_argument('-c', '--cache', action='store_true', help='Generate feed using cached data')
    parser.add_argument('-m', '--max-episodes', type=int, help='Maximum number of episodes')
    parser.add_argument('-a', '--aws-access-id', required=True, help='AWS Access Key ID')
    parser.add_argument('-k', '--aws-secret-key', required=True, help='AWS Secret Key')
    parser.add_argument('-b', '--aws-bucket', required=True, help='AWS S3 Bucket Name')
    args = parser.parse_args()

    bbc_username = args.bbc_username
    bbc_password = args.bbc_password
    foreground = args.show_browser
    output_dir = args.output_dir
    podcast_path = args.podcast_path
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
        DRIVER = initialise_selenium(foreground)
        bbc_login(bbc_username, bbc_password)
        accept_cookie_prompt()
        episodes = get_episodes(max_episodes)

        if not foreground:
            clean_up_selenium()

        download_episodes(episodes)

    create_rss_feed(episodes, podcast_path)
    sync_with_s3(episodes, aws_access_id, aws_secret_key, aws_bucket_name)


if __name__ == '__main__':
    main()
