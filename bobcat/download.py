"""Various utility methods for downloading files"""

import logging
import shutil
import requests
from yt_dlp import YoutubeDL
from .config import CONFIG


def download_file(url: str, output_filename: str) -> None:
    """Download a url to a file"""

    response = requests.get(url, stream=True, timeout=CONFIG.request_timeout)

    with open(output_filename, 'wb') as output_file:
        shutil.copyfileobj(response.raw, output_file)

    logging.debug('Downloaded %s to file %s', url, output_filename)


def download_streaming_audio(url: str, output_filename: str) -> None:
    """Download streaming audio from a page to an m4a file"""

    logger = logging.getLogger('youtube-dl')

    ydl_options = {
        'outtmpl': output_filename,
        'format': 'bestaudio[ext=m4a]',
        'logger': logger,
        'noprogress': True
    }

    with YoutubeDL(ydl_options) as ydl:
        ydl.download([url])

    logging.debug('Downloaded audio from %s to file %s', url, output_filename)
