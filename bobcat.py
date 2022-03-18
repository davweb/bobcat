import argparse
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
URL_BBC_MY_SOUNDS = 'https://www.bbc.co.uk/sounds/my'


def bbc_login(driver, bbc_username, bbc_password):
    """Login in to the BBC site"""

    driver.get(URL_BBC_LOGIN)
    username_field = driver.find_element(By.ID, 'user-identifier-input')
    username_field.send_keys(bbc_username)
    password_field = driver.find_element(By.ID, 'password-input')
    password_field.send_keys(bbc_password)
    submit_button = driver.find_element(By.ID, 'submit-button')
    submit_button.click()


def get_episode_id(url):
    return url.split('/')[-1]


def get_episodes(driver):
    """Get the URLs for episodes of shows I'm subscribed to"""
    episode_urls = []

    driver.get(URL_BBC_MY_SOUNDS)

    # Click on the accept cookies prompt if it is displayed
    accept_cookies = driver.find_elements(By.CSS_SELECTOR, '#bbccookies-continue-button')
    
    if accept_cookies:
        accept_cookies[0].click()

    page = 1

    while True:
        locations = driver.find_elements(By.CSS_SELECTOR, 'div.sounds-react-app li a[href*="/play/"]')
        page_episode_urls = [anchor.get_attribute('href') for anchor in locations]
        print(f'Found {len(page_episode_urls)} episodes on page {page}')
        episode_urls += page_episode_urls
        next_button = driver.find_elements(By.CSS_SELECTOR, 'a.sc-c-pagination-button__paddle .sc-c-icon--chevron-right')

        if not next_button:
            break

        next_button[0].click()
        time.sleep(5)
        page += 1

    return episode_urls


def get_episode_metadata(driver, url, output_dir):
    """Get metadata from local cache or from website"""

    episode_id = get_episode_id(url)
    metadata_directory = f'{output_dir}/{episode_id}'
    metadata_filename = f'{metadata_directory}/episode.json'

    try:
        with open(metadata_filename, 'r') as metadata:
            episode_metadata = json.loads(metadata.read())
            print(f'Read metadata for {episode_id} from file {metadata_filename}')
    except Exception as e:
        episode_metadata = fetch_episode_metadata(driver, url)
        Path(metadata_directory).mkdir(parents=True, exist_ok=True)
        with open(metadata_filename, 'w') as metadata:
            metadata.write(json.dumps(episode_metadata))
        print(f'Read metadata for {episode_id} from website')

    return episode_metadata


def fetch_episode_metadata(driver, url):
    """Get information about an episode from the BBC Sounds website"""
    
    driver.get(url)

    try:
        show_more = driver.find_element(By.CLASS_NAME, 'sc-c-synopsis__button')
        show_more.click()
    except NoSuchElementException:
        pass

    heading = driver.find_element(By.CSS_SELECTOR, '.sc-c-herospace__details-titles .sc-u-screenreader-only')
    title = heading.text
    synopsis = driver.find_element(By.CLASS_NAME, 'sc-c-synopsis')
    description = synopsis.text
    
    return {
        'id': get_episode_id(url),
        'url': url,
        'title': title,
        'description': description
    }


def fetch_new_episodes(foreground, bbc_username, bbc_password, output_dir):
    """Use Selenium to get episodes of the shows subscribed to"""

    chrome_options = Options()

    if foreground:
        chrome_options.add_experimental_option('detach', True)
    else:
        chrome_options.add_argument('--headless')

    chromedriver_path = os.path.join((os.path.dirname(os.path.realpath(__file__))), 'chromedriver')
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1024, 1280)

    bbc_login(driver, bbc_username, bbc_password)
    episode_urls = get_episodes(driver)
    
    episodes = [get_episode_metadata(driver, url, output_dir) for url in episode_urls]

    if not foreground:
        driver.close()

    return episodes


def download_episodes(episodes, output_dir):
    """Download audio files for each episode"""

    for episode in episodes:
        filename = f'{output_dir}/{episode["id"]}/audio.m4a'

        ydl_options = {
            'outtmpl': filename,
            'format': 'm4a'
        }
        
        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            # This automatically skips if file is already downloaded
            result = ydl.download([episode['url']])




def main():
    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-u', '--bbc-username', help='BBC account username or email')
    parser.add_argument('-p', '--bbc-password', help='BBC account password')
    parser.add_argument('-b', '--show-browser', action='store_true', help='Show automation browser in the foreground')
    parser.add_argument('-o', '--output-dir', help='Output Directory')
    args = parser.parse_args()

    bbc_username = args.bbc_username
    bbc_password = args.bbc_password
    foreground = args.show_browser
    output_dir = args.output_dir

    if not bbc_username or not bbc_password:
        raise ValueError('Missing BBC credentials')

    episodes = fetch_new_episodes(foreground, bbc_username, bbc_password, output_dir)
    # download_episodes(episodes, output_dir)    

if __name__ == '__main__':
    main()
