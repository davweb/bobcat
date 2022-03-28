"""Sync local files with Amazon S3"""

import os
from functools import cache
import hashlib
import logging
import boto3

@cache
def _file_md5(filename):
    """Calculate an MD5 hash of a file

    This calcates the MD5 hash of a file in the current working directory.
    Hashes are cached as they won't change during the runtime of the script.
    """

    with open(filename, 'rb') as file:
        file_hash = hashlib.md5()
        while chunk := file.read(8192):
            file_hash.update(chunk)

    return file_hash.hexdigest()


def _get_content_type(filename):
    """Determine the mime type of each file its extension.

    This guesses the mime type of a file by its extension.  As we know the small
    set of file types we'll be uploading this is probably the most accurate way
    to do this.
    """

    if filename.endswith('.xml'):
        return 'application/rss+xml'

    if filename.endswith('.mp3'):
        return 'audio/mpeg'

    if filename.endswith('.jpg'):
        return 'image/jpeg'

    if filename.endswith('.png'):
        return 'image/png'

    raise ValueError(f'Could not determine content type for file "{filename}"')


def bucket_url():
    """Return URL for accessing S3 bucket"""

    s3_bucket_name = os.environ['S3_BUCKET_NAME']
    return f'https://{s3_bucket_name}.s3.amazonaws.com'


def files_with_bucket(files_to_sync):
    """Sync list of files with an s3 bucket

    This syncs a list of filenames which should be files in the current working
    directory with the named S3 bucket.  Missing files are uploaded and unlisted
    files in the bucket are deleted.  An 'md5' custom metadata attribute is
    added on upload to determine if files existing in the bucket have changed.
    """

    aws_access_id = os.environ['AWS_ACCESS_ID']
    aws_secret_key = os.environ['AWS_SECRET_KEY']
    s3_bucket_name = os.environ['S3_BUCKET_NAME']

    s3_client = boto3.resource('s3', aws_access_key_id=aws_access_id, aws_secret_access_key=aws_secret_key)
    bucket = s3_client.Bucket(s3_bucket_name)
    uploaded = set(object.key for object in bucket.objects.all())

    to_upload = files_to_sync - uploaded
    to_delete = uploaded - files_to_sync
    to_check = files_to_sync & uploaded

    # Check if existing files need to be overwritten by comparing local MD5 with
    # that stored as custom metadata on the S3 object
    for filename in to_check:
        remote_file = s3_client.Object(s3_bucket_name, filename)
        remote_md5 = remote_file.metadata.get('md5')
        local_md5 = _file_md5(filename)

        if remote_md5 == local_md5:
            logging.debug('Skipping %s as unmodified since last upload', filename)
        else:
            to_upload.add(filename)

    logging.info('Uploading %d files to S3 Bucket %s', len(to_upload), s3_bucket_name)

    for filename in to_upload:
        bucket.upload_file(filename, filename,
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': _get_content_type(filename),
                'Metadata': {'md5': _file_md5(filename)}
            }
        )
        logging.debug('Uploaded %s to S3 Bucket %s', filename, s3_bucket_name)

    if to_delete:
        objects_to_delete = [{'Key': filename} for filename in to_delete]
        bucket.delete_objects(Delete={'Objects': objects_to_delete})
        logging.info('Removed %s from S3 Bucket %s', ','.join(to_delete), s3_bucket_name)
