"""A collection of utility audio functions"""

import logging
import os
import subprocess

TEMP_FILE = 'temporary.mp3'

def duration_in_seconds(filename):
    """Return the the duration in seconds of an audio file"""

    command = ['ffprobe']

    # only show result and error messages
    command += ['-loglevel', 'error']

    # only out the duration
    command += ['-show_entries', 'format=duration']

    # show the value without labels
    command += ['-print_format', 'default=noprint_wrappers=1:nokey=1']

    # input file
    command += [filename]

    logging.debug('Running command: %s', format(subprocess.list2cmdline(command)))

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    exit_code = result.returncode
    output = result.stdout.strip()
    logging.debug('Output: %s', output)

    if result.stderr:
        logging.debug('Error: %s', result.stderr)

    logging.debug('Command completed with exit code: %d', exit_code)

    if exit_code:
        logging.warning('Failed to run ffprobe for audio file %s', filename)
        return None

    try:
        return int(float(output)) + 1
    except KeyError:
        logging.warning('No duration found for audio file %s', filename)
        return None


def convert_to_mp3(input_filename, output_filename, cover_art, title):
    """Convert an audio file to a 128k CBR MP3 file"""

    command = ['ffmpeg']

    # overwrite existing file
    command += ['-y']

    # input streams and their mapping
    command += ['-i', input_filename]
    command += ['-i', cover_art]
    command += ['-map', '0']
    command += ['-map', '1']

    # 128k CBR MP3 with cover art
    command += ['-b:a', '128k']
    command += ['-f', 'mp3']
    command += ['-codec:v', 'mjpeg']

    # metadata
    command += ['-metadata', 'title={0}'.format(title)]

    # disable writing encoding information as some decoders incorrectly infer VBR if it is there
    command += ['-write_xing', '0']

    # don't show banner
    command += ['-hide_banner']

    # disable stdin so ffmpeg doesn't hang when run from a cron job
    command += ['-nostdin']

    # output file
    command += [TEMP_FILE]

    logging.debug('Running command: %s', format(subprocess.list2cmdline(command)))

    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    for output_line in iter(process.stdout.readline, ""):
        logging.debug('Output: %s', output_line.strip())

    process.stdout.close()
    exit_code = process.wait()

    logging.debug('Command completed with exit code: %d', exit_code)

    if exit_code:
        raise subprocess.CalledProcessError(exit_code, command)

    # Create as temporary file and then rename in case ffmpeg creates incomplete mp3 on a failure
    os.rename(TEMP_FILE, output_filename)

    logging.debug('Converted %s to 128k CBR MP3 %s', input_filename, output_filename)
