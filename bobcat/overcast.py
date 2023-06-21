"""Ping Overcast when feed is updated"""

import logging
import os
from typing import Final
import requests


_OVERCAST_URL: Final = 'https://overcast.fm/ping'
_OVERCAST_PREFIX_PARAM: Final = 'urlprefix'


def ping(feed_url: str) -> None:
    """Ping Overcast with feed Url"""

    if os.environ.get('OVERCAST') is None:
        logging.debug('Overcast ping is not enabled.')
    else:
        logging.debug('Pinging Overcast.')
        result = requests.get(url=_OVERCAST_URL, params={_OVERCAST_PREFIX_PARAM: feed_url}, timeout=60)

        if result.status_code == 200:
            logging.info('Successfully pinged Overcast.')
        else:
            logging.warning('Overcast ping failed with status code %d', result.status_code)
