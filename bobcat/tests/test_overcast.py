"""Unit tests for the Overcast module."""

import unittest
from unittest.mock import patch, MagicMock
from .. import overcast

FEED_URL = 'http://example.com/feed'


class TestOvercast(unittest.TestCase):
    """
    Unit tests for the Overcast module.
    """

    @patch('bobcat.overcast.logging')
    @patch('bobcat.overcast.requests.get')
    @patch('bobcat.overcast.CONFIG')
    def test_ping_disabled(self, mock_config, mock_get, mock_logging):
        """
        Test that ping() does nothing when ping_overcast is True (as per current implementation).
        """
        mock_config.ping_overcast = False

        overcast.ping(FEED_URL)

        mock_get.assert_not_called()
        mock_logging.debug.assert_called_with('Overcast ping is not enabled.')

    @patch('bobcat.overcast.logging')
    @patch('bobcat.overcast.requests.get')
    @patch('bobcat.overcast.CONFIG')
    def test_ping_success(self, mock_config, mock_get, mock_logging):
        """
        Test a successful ping to Overcast.
        """
        mock_config.ping_overcast = True
        mock_config.request_timeout = 10

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        overcast.ping(FEED_URL)

        mock_get.assert_called_once_with(
            url='https://overcast.fm/ping',
            params={'urlprefix': FEED_URL},
            timeout=10
        )
        mock_logging.info.assert_called_with('Successfully pinged Overcast.')

    @patch('bobcat.overcast.logging')
    @patch('bobcat.overcast.requests.get')
    @patch('bobcat.overcast.CONFIG')
    def test_ping_failure(self, mock_config, mock_get, mock_logging):
        """
        Test a failed ping to Overcast.
        """
        mock_config.ping_overcast = True
        mock_config.request_timeout = 15

        status_code = 500
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_get.return_value = mock_response

        overcast.ping(FEED_URL)

        mock_get.assert_called_once_with(
            url='https://overcast.fm/ping',
            params={'urlprefix': FEED_URL},
            timeout=15
        )
        mock_logging.warning.assert_called_with('Overcast ping failed with status code %d', status_code)


if __name__ == '__main__':
    unittest.main()
