import unittest
import time
from unittest.mock import patch, MagicMock

from arr_manager.retention.enumerator import RetentionEnumerator
from arr_manager.retention.config import RetentionSettings
from unittest.mock import MagicMock
class MockAddon:
    def getSetting(self, key):
        return ''

class TestRetentionEnumerator(unittest.TestCase):
    def setUp(self):
        self.kodi_client = MagicMock()
        self.arr_manager = MagicMock()
        self.path_mapper = MagicMock()
        self.logger = MagicMock()
        self.enumerator = RetentionEnumerator(self.kodi_client, self.arr_manager, self.path_mapper, self.logger)
        self.settings = RetentionSettings(MockAddon())
        self.settings.include_movies = True
        self.settings.include_episodes = True

    def test_conservative_date(self):
        self.assertEqual(self.enumerator._get_conservative_added_timestamp([100, 200, 300]), 300)
        self.assertEqual(self.enumerator._get_conservative_added_timestamp([300, None, 100]), 300)
        self.assertEqual(self.enumerator._get_conservative_added_timestamp([None, None, None]), None)

    def test_parse_dates(self):
        self.assertEqual(self.enumerator._parse_kodi_date("2020-01-01 12:00:00"), 1577880000.0)
        self.assertEqual(self.enumerator._parse_arr_date("2020-01-01T12:00:00Z"), 1577880000.0)

    @patch('arr_manager.retention.enumerator.resolve_movie')
    def test_get_movies_paginated(self, mock_resolve_movie):
        # Setup Kodi Client mock to return 2 pages of movies
        def kodi_call_mock(method, params):
            if method == "VideoLibrary.GetMovies":
                start = params["limits"]["start"]
                if start == 0:
                    return {"movies": [{"movieid": i, "title": f"Movie {i}", "playcount": 1, "lastplayed": "2020-01-01 12:00:00"} for i in range(1, 501)]}
                elif start == 500:
                    return {"movies": [{"movieid": 501, "title": "Movie 501", "playcount": 0}]}
            return {}
        self.kodi_client.call = kodi_call_mock

        # Setup resolve mock
        mock_resolve_movie.return_value = {"id": 99, "hasFile": True}
        self.arr_manager.radarr.movie_files.return_value = [{"id": 999, "dateAdded": "2020-01-01T12:00:00Z"}]

        candidates = self.enumerator.get_movies(self.settings)
        self.assertEqual(len(candidates), 501)
        self.assertTrue(candidates[0].watched)
        self.assertFalse(candidates[500].watched)

    @patch('arr_manager.retention.enumerator.resolve_episode_context')
    @patch('arr_manager.retention.enumerator.resolve_series')
    def test_get_episodes_paginated(self, mock_resolve_series, mock_resolve_episode_context):
        def kodi_call_mock(method, params):
            if method == "VideoLibrary.GetEpisodes":
                start = params["limits"]["start"]
                if start == 0:
                    return {"episodes": [{"episodeid": 1, "title": "Ep 1", "playcount": 1, "season": 1, "episode": 1}]}
            return {}
        self.kodi_client.call = kodi_call_mock

        mock_resolve_series.return_value = {"id": 77}
        mock_resolve_episode_context.return_value = (None, None, {"id": 88, "dateAdded": "2020-01-01T12:00:00Z"})

        candidates = self.enumerator.get_episodes(self.settings)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].arr_id, 77)
        self.assertEqual(candidates[0].file_id, 88)

if __name__ == "__main__":
    unittest.main()
