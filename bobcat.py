import argparse
import atexit
import os
import youtube_dl
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


URL_BBC_LOGIN = 'https://account.bbc.com/signin'
URL_BBC_MY_SOUNDS = 'https://www.bbc.co.uk/sounds/my?page={}'


class Episode:
    def __init__(self, url):
        self.url = url
        self.id = url.split('/')[-1]
        self.data_directory = f'{output_dir}/{self.id}'
        self.audio_filename = f'{self.data_directory}/audio.m4a'
        self.metadata_filename = f'{self.data_directory}/episode.json'


    def is_downloaded(self):
        """Returns true if the audio is downloaded for this episode"""

        return Path(self.audio_filename).exists()


    def _read_metadata_file(self):
        with open(self.metadata_filename, 'r') as metadata:
            episode_metadata = json.loads(metadata.read())

        if episode_metadata['id'] != self.id:
            raise ValueError()

        self.title = episode_metadata['title']
        self.description = episode_metadata['description']


    def _write_metadata_file(self):
        episode_metadata = {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'description': self.description
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
        
        self.title = heading.text
        self.description = synopsis.text


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


def get_episodes():
    """Get the episodes of shows subscribed to on BBC Sounds"""

    global driver 

    episode_urls = []
    page = 1

    while True:
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
        page += 1

    episodes  = [Episode(url) for url in episode_urls]

    for episode in episodes:
        episode.load_metadata()

    return episodes


def download_episodes(episodes):
    """Download audio files for each episode"""

    for episode in episodes:
        if episode.is_downloaded():
            print(f'Episode {episode.id} already downloaded')
            continue

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


def main():
    global output_dir

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-u', '--bbc-username', help='BBC account username or email', required=True)
    parser.add_argument('-p', '--bbc-password', help='BBC account password', required=True)
    parser.add_argument('-b', '--show-browser', action='store_true', help='Show automation browser in the foreground')
    parser.add_argument('-o', '--output-dir', help='Output Directory', required=True)
    args = parser.parse_args()

    bbc_username = args.bbc_username
    bbc_password = args.bbc_password
    foreground = args.show_browser
    output_dir = args.output_dir
    
    initialise_selenium(foreground)
    bbc_login(bbc_username, bbc_password)
    episodes = get_episodes()

    if not foreground:
        clean_up_selenium()

    download_episodes(episodes)


if __name__ == '__main__':
    main()
