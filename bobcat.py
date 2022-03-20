import argparse
import atexit
import os
import youtube_dl
import json
import shutil
import time
import pytz
import requests
from pathlib import Path
from datetime import datetime
from feedgen.feed import FeedGenerator
from mutagen.mp4 import MP4
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


URL_BBC_LOGIN = 'https://account.bbc.com/signin'
URL_BBC_SOUNDS = 'https://www.bbc.co.uk/sounds'
URL_BBC_MY_SOUNDS = 'https://www.bbc.co.uk/sounds/my?page={}'


class Episode:
    def __init__(self, url=None, id=None):
        if id:
            self.id = id
        else:
            self.url = url
            self.id = url.split('/')[-1]
        
        self.data_directory = f'{output_dir}/{self.id}'
        self.audio_filename = f'{self.data_directory}/audio.m4a'
        self.metadata_filename = f'{self.data_directory}/episode.json'
        self.image_filename = f'{self.data_directory}/image.jpg'


    def is_audio_downloaded(self):
        """Returns true if the audio is downloaded for this episode"""

        return Path(self.audio_filename).exists()


    def is_image_downloaded(self):
        """Returns true if the audio is downloaded for this episode"""

        return Path(self.image_filename).exists()

    
    def is_downloaded(self):
        """Returns true if the audio and image is downloaded for this episode"""

        return self.is_audio_downloaded() and self.is_image_downloaded()


    def _read_metadata_file(self):
        with open(self.metadata_filename, 'r') as metadata:
            episode_metadata = json.loads(metadata.read())

        if episode_metadata['id'] != self.id:
            raise ValueError()

        self.url = episode_metadata['url']
        self.title = episode_metadata['title']
        self.description = episode_metadata['description']
        self.image_url = episode_metadata['image_url']


    def _write_metadata_file(self):
        episode_metadata = {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'description': self.description,
            'image_url': self.image_url
        }

        Path(self.data_directory).mkdir(parents=True, exist_ok=True)
        with open(self.metadata_filename, 'w') as metadata:
            metadata.write(json.dumps(episode_metadata))


    def load_metadata(self):
        """Get metadata from local cache or from website"""

        global output_dir

        try:
            self._read_metadata_file()
            print(f'Read metadata for {self.id} from file {self.metadata_filename}')
        except:
            self._fetch_metadata()
            self._write_metadata_file()
            print(f'Read metadata for {self.id} from website')


    def _fetch_metadata(self):
        """Get information about an episode from the BBC Sounds website"""
        
        global driver

        driver.get(self.url)

        try:
            show_more = driver.find_element(By.CLASS_NAME, 'sc-c-synopsis__button')
            show_more.click()
        except NoSuchElementException:
            pass

        heading = driver.find_element(By.CSS_SELECTOR, '.sc-c-herospace__details-titles .sc-u-screenreader-only')
        synopsis = driver.find_element(By.CLASS_NAME, 'sc-c-synopsis')
        image = driver.find_element(By.CLASS_NAME, 'sc-c-herospace__image')
        
        title = heading.text
        
        if title.endswith(' - BBC Sounds'):
            title = title[:-13]

        self.title = title
        self.description = synopsis.text
        self.image_url = image.get_attribute('src')


def initialise_selenium(foreground):
    """Initialise the Selenium driver"""
    global driver

    chrome_options = Options()

    if foreground:
        chrome_options.add_experimental_option('detach', True)
    else:
        chrome_options.add_argument('--headless')

    chromedriver_path = os.path.join((os.path.dirname(os.path.realpath(__file__))), 'chromedriver')
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1024, 1280)


def clean_up_selenium():
    global driver

    driver.close()


def bbc_login(bbc_username, bbc_password):
    """Login in to the BBC site"""

    driver.get(URL_BBC_LOGIN)
    username_field = driver.find_element(By.ID, 'user-identifier-input')
    username_field.send_keys(bbc_username)
    password_field = driver.find_element(By.ID, 'password-input')
    password_field.send_keys(bbc_password)
    submit_button = driver.find_element(By.ID, 'submit-button')
    submit_button.click()


def get_episodes(max_episodes):
    """Get the episodes of shows subscribed to on BBC Sounds"""

    global driver 

    episode_urls = []
    page = 0

    while True:
        page += 1
        driver.get(URL_BBC_MY_SOUNDS.format(page))

        # Click on the accept cookies prompt if it is displayed
        accept_cookies = driver.find_elements(By.CSS_SELECTOR, '#bbccookies-continue-button')
    
        if accept_cookies:
            accept_cookies[0].click()

        locations = driver.find_elements(By.CSS_SELECTOR, 'div.sounds-react-app li a[href*="/play/"]')
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


def download_episode_image(episode):
    """Download the image files for each episode"""

    if episode.is_image_downloaded():
        print(f'Image for episode {episode.id} already downloaded')
    else:
        response = requests.get(episode.image_url, stream=True)
        with open(episode.image_filename, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)

        print(f'Image for episode {episode.id} downloaded from website')


def download_episode_audio(episode):
    """Download audio files for each episode"""

    if episode.is_audio_downloaded():
        print(f'Audio for episode {episode.id} already downloaded')
    else:
        ydl_options = {
            'outtmpl': episode.audio_filename,
            'format': 'm4a'
        }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            
            try:
                # This automatically skips if file is already downloaded
                ydl.download([episode.url])
            except Exception as e:
                print(repr(e))


def load_episodes():
    """Create episodes from local data rather than the BBC Sounds website"""

    episodes = []

    for dir, _, files in os.walk(output_dir):
        if 'episode.json' in files:
            episode_id = Path(dir).relative_to(output_dir).name
            episode = Episode(id=episode_id)
            episode.load_metadata()
            episodes.append(episode)

    return episodes


def create_rss_feed(episodes, podcast_path):
    global output_dir

    shutil.copy2('logo.png', output_dir)
    logo_url = f'{podcast_path}/logo.png'

    episodes = (episode for episode in episodes if episode.is_downloaded())

    fg = FeedGenerator()
    fg.load_extension('podcast')

    fg.title('BBC Sounds Subscriptions')
    fg.description('Episodes of shows I have subscribed to on BBC Sounds')
    fg.author({'name': 'BBC Sounds', 'email': 'sounds@bbc.co.uk'})
    fg.logo(f'{podcast_path}/logo.png')
    fg.link(href=f'{podcast_path}/podcast.xml', rel='self')
    fg.language('en')

    fg.podcast.itunes_category('Arts')
    fg.podcast.itunes_category('Comedy')
    fg.podcast.itunes_category('Music')
    fg.podcast.itunes_category('News')
    fg.podcast.itunes_category('Sports')
    fg.podcast.itunes_author('BBC Sounds')
    fg.podcast.itunes_block(True)
    fg.podcast.itunes_explicit('no')
    fg.podcast.itunes_image(logo_url)
    fg.podcast.itunes_owner(name='BBC Sounds', email='sounds@bbc.co.uk')

    for episode in episodes:
        size_in_bytes = os.path.getsize(episode.audio_filename)
        mtime = os.path.getmtime(episode.audio_filename)
        published = datetime.fromtimestamp(mtime, pytz.utc)
        audio = MP4(episode.audio_filename)
        duration_in_seconds = int(audio.info.length)
        audio_url = f'{podcast_path}/{episode.audio_filename}'
        image_url = f'{podcast_path}/{episode.image_filename}'

        fe = fg.add_entry()
        fe.id(audio_url)
        fe.title(episode.title)
        fe.description(episode.description)
        fe.enclosure(url=audio_url, length=str(size_in_bytes), type='audio/mpeg')
        fe.published(published)
        fe.podcast.itunes_duration(duration_in_seconds)
        fe.podcast.itunes_image(image_url)

    fg.rss_str(pretty=True)
    fg.rss_file(f'{output_dir}/podcast.xml')


# def copy_to_s3(episodes):
#     import boto
#     s3 = boto.connect_s3()


def main():
    global output_dir

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-u', '--bbc-username', required=True, help='BBC account username or email')
    parser.add_argument('-p', '--bbc-password', required=True, help='BBC account password')
    parser.add_argument('-b', '--show-browser', action='store_true', help='Show automation browser in the foreground')
    parser.add_argument('-o', '--output-dir', required=True, help='Output Directory')
    parser.add_argument('-x', '--podcast-path', required=True, help='Podcast Path Prefix')
    parser.add_argument('-c', '--cache', action='store_true', help='Generate feed using cached data')
    parser.add_argument('-m', '--max_episodes', type=int, help='Maximum number of episodes')
    args = parser.parse_args()

    bbc_username = args.bbc_username
    bbc_password = args.bbc_password
    foreground = args.show_browser
    output_dir = args.output_dir
    podcast_path = args.podcast_path
    cache = args.cache
    max_episodes = args.max_episodes

    if cache:
        episodes = load_episodes()
    else:
        initialise_selenium(foreground)
        bbc_login(bbc_username, bbc_password)
        episodes = get_episodes(max_episodes)

        if not foreground:
            clean_up_selenium()

        download_episodes(episodes)

    create_rss_feed(episodes, podcast_path)
    # copy_to_s3(episodes)


if __name__ == '__main__':
    main()
