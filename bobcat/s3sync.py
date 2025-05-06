"""Sync local files with Amazon S3"""

import logging
from typing import Any, Iterable
import boto3
from .config import CONFIG


def _get_content_type(filename: str) -> str:
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


def bucket_url() -> str:
    """Return URL for accessing S3 bucket"""

    return f'https://{CONFIG.s3_bucket_name}.s3.amazonaws.com'


def _get_bucket_client() -> Any:
    """Return a client for accessing an S3 Bucket"""

    s3_client = boto3.resource('s3',
                               aws_access_key_id=CONFIG.aws_access_id,
                               aws_secret_access_key=CONFIG.aws_secret_key)
    return s3_client.Bucket(CONFIG.s3_bucket_name)


def get_bucket_contents() -> set[str]:
    """Return all the keys for an S3 Bucket"""

    bucket = _get_bucket_client()
    return set(object.key for object in bucket.objects.all())


def upload_file(filename: str) -> None:
    """Upload a file to the S3 Bucket"""

    upload_files([filename])


def upload_files(filenames: Iterable[str]) -> None:
    """Upload files to the S3 Bucket"""

    logging.info('Uploading %s to S3 Bucket %s', ','.join(filenames), CONFIG.s3_bucket_name)
    bucket = _get_bucket_client()

    for filename in filenames:
        bucket.upload_file(filename, filename,
                           ExtraArgs={
                               'ACL': 'public-read',
                               'ContentType': _get_content_type(filename)
                           }
                           )


def delete_files(filenames: Iterable[str]) -> None:
    """Delete files from S3 bucket"""

    logging.info('Removing %s from S3 Bucket %s', ','.join(filenames), CONFIG.s3_bucket_name)

    bucket = _get_bucket_client()
    objects_to_delete = [{'Key': filename} for filename in filenames]
    bucket.delete_objects(Delete={'Objects': objects_to_delete})
