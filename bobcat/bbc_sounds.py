"""Fetch Episode data from BBC Sounds"""

import atexit
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Final
from dateutil import parser
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
import user_agent

_URL_BBC_LOGIN: Final = 'https://account.bbc.com/signin'
_URL_BBC_SOUNDS: Final = 'https://www.bbc.co.uk/sounds'
_URL_BBC_MY_SOUNDS: Final = 'https://www.bbc.co.uk/sounds/my?page={}'

# For the container we can use the default chromedriver installed by apk
#  For development we can get webdriver-manager to download it for us
_DEFAULT_CHROMEDRIVER_PATH: Final = '/usr/bin/chromedriver'
_USE_DEFAULT_CHROMEDRIVER: Final = Path(_DEFAULT_CHROMEDRIVER_PATH).exists()

if not _USE_DEFAULT_CHROMEDRIVER:
    from webdriver_manager.chrome import ChromeDriverManager

_DRIVER: WebDriver | None = None


def _get_driver() -> WebDriver:
    """Initialise the Selenium driver"""

    global _DRIVER

    if _DRIVER is None:
        chrome_options = Options()
        foreground = 'SHOW_BROWSER' in os.environ

        if foreground:
            chrome_options.add_experimental_option('detach', True)
        else:
            # Run headless
            chrome_options.add_argument('--headless')

            # these options improve performance in a container
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')

            # these options required to get chrome working in the Alpine docker container
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')

            #  hide that we're automated
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            spoof_user_agent = user_agent.generate_user_agent(os='mac', navigator='chrome')
            chrome_options.add_argument(f'--user-agent={spoof_user_agent}')
            logging.info(spoof_user_agent)

            atexit.register(clean_up)

        if _USE_DEFAULT_CHROMEDRIVER:
            service = Service(_DEFAULT_CHROMEDRIVER_PATH)
        else:
            service = Service(ChromeDriverManager().install())

        _DRIVER = webdriver.Chrome(options=chrome_options, service=service)
        _DRIVER.set_window_size(1024, 1280)

        # TODO - add screenshot capture properly
        # try:
        _bbc_login()
        _accept_cookie_prompt()
        # except NoSuchElementException:
        #     logging.exception('Failed to find an expected element')
        #     _DRIVER.get_screenshot_as_file('/bobcat/error.png')
        #     sys.exit(1)

    return _DRIVER


def clean_up() -> None:
    """Tidy up Selenium resources"""

    global _DRIVER

    if _DRIVER is not None:
        _DRIVER.quit()
        _DRIVER = None


def _bbc_login() -> None:
    """Login in to the BBC site"""

    bbc_username = os.environ['BBC_EMAIL']
    bbc_password = os.environ['BBC_PASSWORD']

    driver = _get_driver()
    driver.get(_URL_BBC_LOGIN)

    try:
        username_field = driver.find_element(By.ID, 'user-identifier-input')
    except NoSuchElementException:
        username_field = driver.find_element(By.CSS_SELECTOR, '[data-testid="input"]')

    username_field.send_keys(bbc_username)
    submit_button = driver.find_element(By.ID, 'submit-button')
    submit_button.click()

    try:
        password_field = driver.find_element(By.ID, 'password-input')
    except NoSuchElementException:
        password_field = driver.find_element(By.CSS_SELECTOR, '[data-testid="input"]')

    password_field.send_keys(bbc_password)
    submit_button = driver.find_element(By.ID, 'submit-button')
    submit_button.click()

    if driver.current_url.startswith(_URL_BBC_LOGIN):
        logging.error('BBC login failed. Are the credentials correct?')
        sys.exit(1)


def _accept_cookie_prompt() -> None:
    """Click on the accept cookies prompt"""

    driver = _get_driver()
    driver.get(_URL_BBC_SOUNDS)
    accept_cookies = driver. find_elements(By.CSS_SELECTOR, '#bbccookies-accept-button')

    if len(accept_cookies) == 0:
        accept_cookies = driver.find_elements(By.CSS_SELECTOR, '[data-testid="accept-button"]')

    accept_cookies[0].click()


def get_episode_urls(max_episodes: int) -> list[str]:
    """Get the episodes of shows subscribed to on BBC Sounds"""

    driver = _get_driver()
    episode_urls = []
    page = 0

    while True:
        page += 1
        logging.debug('Opening page %d', page)
        driver.get(_URL_BBC_MY_SOUNDS.format(page))
        locations = driver.find_elements(
            By.CSS_SELECTOR, 'main li a[href*="/play/"]')

        page_episode_urls = []

        for anchor in locations:
            href = anchor.get_attribute('href')

            if href:
                page_episode_urls.append(href)

        episode_count = len(page_episode_urls)

        if episode_count == 0:
            break

        logging.debug('Found %d episodes on page %d', episode_count, page)
        episode_urls += page_episode_urls

        if len(episode_urls) >= max_episodes:
            episode_urls = episode_urls[:max_episodes]
            break

    return episode_urls


def get_episode_metadata(url: str) -> dict[str, str | datetime]:
    """Get the metadata for an episode of a show on BBC Sounds"""

    driver = _get_driver()
    driver.get(url)

    data = driver.execute_script('return window.__PRELOADED_STATE__;')  # type: ignore
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
