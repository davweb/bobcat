"""Ping Overcast when feed is updated"""

import logging
import os
import requests

_OVERCAST_URL = 'https://overcast.fm/ping?urlprefix={}'

def ping(feed_url):
    """Ping Overcast with feed Url"""

    if os.environ.get('OVERCAST') is None:
        logging.debug('Overcast ping is not enabled.')
    else:
        url = _OVERCAST_URL.format(requests.utils.quote(feed_url))
        logging.debug('Pinging Overcast at "%s"', url)
        result = requests.get(url)

        if result.status_code == 200:
            logging.info('Successfully pinged Overcast.')
        else:
            logging.warning('Overcast ping failed with status code %d', result.status_code)
