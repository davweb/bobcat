"""Sync local files with Amazon S3"""

import os
import logging
import boto3


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


def _bucket_name():
    """Return S3 bucket name"""

    return os.environ['S3_BUCKET_NAME']


def bucket_url():
    """Return URL for accessing S3 bucket"""

    s3_bucket_name = _bucket_name()
    return f'https://{s3_bucket_name}.s3.amazonaws.com'


def _get_bucket_client():
    """Return a client for accessing an S3 Bucket"""

    aws_access_id = os.environ['AWS_ACCESS_ID']
    aws_secret_key = os.environ['AWS_SECRET_KEY']
    s3_bucket_name = _bucket_name()

    s3_client = boto3.resource('s3', aws_access_key_id=aws_access_id,
                               aws_secret_access_key=aws_secret_key)
    return s3_client.Bucket(s3_bucket_name)


def get_bucket_contents():
    """Return all the keys for an S3 Bucket"""

    bucket = _get_bucket_client()
    return set(object.key for object in bucket.objects.all())


def upload_file(filename):
    """Upload a file to the S3 Bucket"""

    upload_files([filename])


def upload_files(filenames):
    """Upload files to the S3 Bucket"""

    logging.info('Uploading %s to S3 Bucket %s', ','.join(filenames), _bucket_name())
    bucket = _get_bucket_client()

    for filename in filenames:
        bucket.upload_file(filename, filename,
                           ExtraArgs={
                               'ACL': 'public-read',
                               'ContentType': _get_content_type(filename)
                           }
                           )


def delete_files(filenames):
    """Delete files from S3 bucket"""

    logging.info('Removing %s from S3 Bucket %s', ','.join(filenames), _bucket_name())

    bucket = _get_bucket_client()
    objects_to_delete = [{'Key': filename} for filename in filenames]
    bucket.delete_objects(Delete={'Objects': objects_to_delete})
