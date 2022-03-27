"""Fetch Episode data from BBC Sounds"""

import atexit
import logging
import os
from dateutil import parser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bobcat import download

_URL_BBC_LOGIN = 'https://account.bbc.com/signin'
_URL_BBC_SOUNDS = 'https://www.bbc.co.uk/sounds'
_URL_BBC_MY_SOUNDS = 'https://www.bbc.co.uk/sounds/my?page={}'

_DRIVER = None

def _get_driver():
    """Initialise the Selenium driver"""

    global _DRIVER

    if _DRIVER is None:
        chrome_options = Options()
        foreground = 'SHOW_BROWSER' in os.environ

        if foreground:
            chrome_options.add_experimental_option('detach', True)
        else:
            chrome_options.add_argument('--headless')
            atexit.register(clean_up_selenium)

        service = Service(ChromeDriverManager().install())
        _DRIVER = webdriver.Chrome(service=service, options=chrome_options)
        _DRIVER.set_window_size(1024, 1280)

        _bbc_login()
        _accept_cookie_prompt()

    return _DRIVER


def clean_up_selenium():
    """Tidy up Selenium resources"""
    _DRIVER.quit()


def _bbc_login():
    """Login in to the BBC site"""

    bbc_username = os.environ['BBC_EMAIL']
    bbc_password = os.environ['BBC_PASSWORD']

    driver = _get_driver()
    driver.get(_URL_BBC_LOGIN)
    username_field = driver.find_element(By.ID, 'user-identifier-input')
    username_field.send_keys(bbc_username)
    password_field = driver.find_element(By.ID, 'password-input')
    password_field.send_keys(bbc_password)
    submit_button = driver.find_element(By.ID, 'submit-button')
    submit_button.click()


def _accept_cookie_prompt():
    """Click on the accept cookies prompt"""

    driver = _get_driver()
    driver.get(_URL_BBC_SOUNDS)
    accept_cookies = driver.find_elements(By.CSS_SELECTOR, '#bbccookies-continue-button')
    accept_cookies[0].click()


def get_episode_urls(max_episodes):
    """Get the episodes of shows subscribed to on BBC Sounds"""

    driver = _get_driver()
    episode_urls = []
    page = 0

    while True:
        page += 1
        driver.get(_URL_BBC_MY_SOUNDS.format(page))
        locations = driver.find_elements(By.CSS_SELECTOR, 'div.sounds-react-app li a[href*="/play/"]')
        page_episode_urls = [anchor.get_attribute('href') for anchor in locations]
        episode_count = len(page_episode_urls)

        if episode_count == 0:
            break

        logging.info('Found %d episodes on page %d', episode_count, page)
        episode_urls += page_episode_urls

        if len(episode_urls) >= max_episodes:
            episode_urls = episode_urls[:max_episodes]
            break

    return episode_urls


def get_episode_metadata(url):
    """Get the metadata for an episode of a show on BBC Sounds"""

    driver = _get_driver()
    driver.get(url)

    data = driver.execute_script('return window.__PRELOADED_STATE__;')
    programme = data['programmes']['current']

    titles = programme['titles']
    title = titles['primary']

    if titles['secondary'] is not None:
        title += ' - ' + titles['secondary']

    if titles['tertiary'] is not None:
        title += ' - ' + titles['tertiary']

    description = None
    synopses = programme['synopses']

    for kind in ['long', 'medium', 'short']:
        synopsis = synopses[kind]

        if synopsis is not None:
            description = synopsis
            break

    if description is None:
        logging.warning('Did not find description on page %s', url)

    image_url = programme['image_url'].replace('{recipe}', '1600x1600')
    availability_from = parser.parse(programme['availability']['from'])

    # Navigate away from programme page so audio doesn't start playing
    driver.get(_URL_BBC_SOUNDS)

    return {
        'title': title,
        'synopsis': synopsis,
        'image_url': image_url,
        'availability_from': availability_from
    }
