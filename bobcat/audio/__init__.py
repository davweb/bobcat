"""A collection of utility audio functions"""

import logging
import pydub

def duration_in_seconds(filename):
    """Return the the duration in seconds of an audio file"""

    info = pydub.utils.mediainfo(filename)

    try:
        return int(float(info['duration'])) + 1
    except KeyError:
        logging.warning('No duration found for audio file %s', filename)
        return None


def convert_to_mp3(input_filename, output_filename, cover_art, title):
    """Convert an audio file to a 128k CBR MP3 file"""

    audio_segment = pydub.AudioSegment.from_file(input_filename)
    tags={'title': title}

    # disable writing encoding information as some decoders incorrectly infer VBR if it is there
    parameters = ['-write_xing','0']

    audio_segment.export(output_filename, format='mp3', bitrate='128k',
        tags=tags, cover=cover_art, parameters=parameters)

    logging.info('Converted %s to 128k CBR MP3 %s', input_filename, output_filename)
