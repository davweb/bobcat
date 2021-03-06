"""Various utility methods for downloading files"""

import logging
import shutil
import requests
import youtube_dl


def download_file(url, output_filename):
    """Download a url to a file"""

    response = requests.get(url, stream=True)

    with open(output_filename, 'wb') as output_file:
        shutil.copyfileobj(response.raw, output_file)

    logging.debug('Downloaded %s to file %s', url, output_filename)


def download_streaming_audio(url, output_filename):
    """Download streaming audio from a page to an m4a file"""

    logger = logging.getLogger('youtube-dl')

    ydl_options = {
        'outtmpl': output_filename,
        'format': 'bestaudio[ext=m4a]',
        'logger': logger,
        'noprogress': True
    }

    with youtube_dl.YoutubeDL(ydl_options) as ydl:
        ydl.download([url])

    logging.debug('Downloaded audio from %s to file %s', url, output_filename)
