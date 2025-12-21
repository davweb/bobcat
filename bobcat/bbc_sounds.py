"""Fetch Episode data from BBC Sounds"""

import atexit
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Final
from dateutil import parser
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import user_agent
from .config import CONFIG

_URL_BBC_LOGIN: Final = 'https://account.bbc.com/signin'
_URL_BBC_SOUNDS: Final = 'https://www.bbc.co.uk/sounds'
_URL_BBC_MY_SOUNDS: Final = 'https://www.bbc.co.uk/sounds/my?page={}'

# For the container we can use the default chromedriver installed by apt
# For development we can get webdriver-manager to download it for us
_DEFAULT_CHROMEDRIVER_PATH: Final = '/usr/bin/chromedriver'

if Path(_DEFAULT_CHROMEDRIVER_PATH).exists():
    SERVICE = Service(_DEFAULT_CHROMEDRIVER_PATH)
else:
    from webdriver_manager.chrome import ChromeDriverManager
    SERVICE = Service(ChromeDriverManager().install())

_DRIVER: WebDriver | None = None


def _get_driver() -> WebDriver:
    """Initialise the Selenium driver"""

    global _DRIVER

    if _DRIVER is None:
        chrome_options = Options()

        if CONFIG.show_browser:
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

            atexit.register(clean_up)

        _DRIVER = webdriver.Chrome(options=chrome_options, service=SERVICE)
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

    driver = _get_driver()
    driver.get(_URL_BBC_LOGIN)
    wait = WebDriverWait(driver, 10)

    try:
        username_field = wait.until(EC.any_of(
            EC.presence_of_element_located((By.ID, 'username')),
            EC.presence_of_element_located((By.ID, 'user-identifier-input'))
        ))
    except TimeoutException:
        logging.error('Did not find username field for BBC login')
        sys.exit(1)

    username_field.send_keys(CONFIG.bbc_username)

    submit_button = wait.until(EC.element_to_be_clickable((By.ID, 'submit-button')))
    submit_button.click()

    try:
        password_field = wait.until(EC.any_of(
            EC.presence_of_element_located((By.ID, 'password')),
            EC.presence_of_element_located((By.ID, 'password-input'))
        ))
    except TimeoutException:
        logging.error('Did not find password field for BBC login')
        sys.exit(1)

    password_field.send_keys(CONFIG.bbc_password)

    submit_button = wait.until(EC.element_to_be_clickable((By.ID, 'submit-button')))
    submit_button.click()

    if driver.current_url.startswith(_URL_BBC_LOGIN):
        logging.error('BBC login failed. Are the credentials correct?')
        sys.exit(1)


def _accept_cookie_prompt() -> None:
    """Click on the accept cookies prompt"""

    driver = _get_driver()
    driver.get(_URL_BBC_SOUNDS)
    wait = WebDriverWait(driver, 10)

    try:
        accept_cookies = wait.until(EC.any_of(
            EC.element_to_be_clickable((By.ID, 'bbccookies-accept-button')),
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="accept-button"]'))
        ))
    except TimeoutException:
        logging.error('Did not find BBC cookie banner')
        sys.exit(1)

    accept_cookies.click()


def get_episode_urls() -> list[str]:
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

        if len(episode_urls) >= CONFIG.max_episodes:
            episode_urls = episode_urls[:CONFIG.max_episodes]
            break

    return episode_urls


def get_episode_metadata(url: str) -> dict[str, str | datetime]:
    """Get the metadata for an episode of a show on BBC Sounds"""

    driver = _get_driver()
    driver.get(url)

    programme = driver.execute_script("""
        let dehydratedQueries = window.__NEXT_DATA__.props.pageProps.dehydratedState.queries;
        let pageData = dehydratedQueries.filter(q => q.queryKey[0].startsWith('/v2/my/experience/inline/play/'))[0].state.data.data;
        let episodeData = pageData.filter(q => q.id == 'aod_play_area')[0].data[0];
        return episodeData;
        """)  # type: ignore

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
