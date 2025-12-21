# -*- coding: utf-8 -*-
"""Merge bobcat configuration from the command line, enviroment and config files"""

import argparse
import os
from pathlib import Path
import sys


def _get_arguments() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description='Convert BBC Sounds subscription to an RSS Feed.')
    parser.add_argument('-o', '--output-dir', required=True, help='Output Directory')
    parser.add_argument('-n', '--no-episode-refresh', action='store_true',
                        help='Generate feed using only cached episode data')
    parser.add_argument('-l', '--logfile', type=Path)
    return parser.parse_args()


class Config:
    """Configuration class"""

    @staticmethod
    def is_running_in_test() -> bool:
        """
        Returns True if the code is running under a pytest test session.
        """
        return "pytest" in sys.modules or "unittest" in sys.modules

    def __init__(self) -> None:
        if not Config.is_running_in_test():
            self._args = _get_arguments()
        else:
            # In a test environment, provide a default Namespace.
            # Tests can patch properties as needed.
            self._args = argparse.Namespace(
                output_dir=None,
                no_episode_refresh=False,
                logfile=None,
            )

    @property
    def request_timeout(self) -> int:
        """Return the HTTP request timeout"""
        return 60

    @property
    def output_dir(self) -> Path:
        """Return the output directory for the script"""
        return self._args.output_dir

    @property
    def cache_only(self) -> bool:
        """Should be update subscriptions or just rebuild podcast XML from the cache"""

        return self._args.no_episode_refresh

    @property
    def max_episodes(self) -> int:
        """Return the maximum number of episodes to have in the feed"""

        return int(os.environ.get('EPISODE_LIMIT', '20'))

    @property
    def logfile(self) -> Path:
        """Return the logfile location"""

        return self._args.logfile

    @property
    def log_level(self) -> str:
        """Return the log level name"""

        return os.environ.get('LOG_LEVEL', 'INFO')

    @property
    def library_log_level(self) -> str:
        """Return the library log level name"""

        return os.environ.get('LIBRARY_LOG_LEVEL', 'CRITICAL')

    @property
    def show_browser(self) -> bool:
        """Show the browser being used for automations"""

        return 'SHOW_BROWSER' in os.environ

    @property
    def bbc_username(self) -> str:
        """Return the BBC username"""

        return os.environ['BBC_EMAIL']

    @property
    def bbc_password(self) -> str:
        """Return the BBC password"""

        return os.environ['BBC_PASSWORD']

    @property
    def ping_overcast(self) -> bool:
        """Ping Overcast servers when feed is updated"""

        return 'OVERCAST' in os.environ

    @property
    def s3_bucket_name(self) -> str:
        """Return the AWS S3 bucket name"""

        return os.environ['S3_BUCKET_NAME']

    @property
    def aws_access_id(self) -> str:
        """Return the AWS access ID"""

        return os.environ['AWS_ACCESS_ID']

    @property
    def aws_secret_key(self) -> str:
        """Return the AWS secret key"""

        return os.environ['AWS_SECRET_KEY']

    @property
    def database_dir(self) -> str:
        """Return the database directory"""

        return os.environ['DATABASE_DIRECTORY']


CONFIG = Config()
