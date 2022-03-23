"""A collection of utility audio functions"""

import pydub

def duration_in_seconds(filename):
    """Return the the duration in seconds of an audio file"""

    info = pydub.utils.mediainfo(filename)
    return int(float(info['duration'])) + 1
