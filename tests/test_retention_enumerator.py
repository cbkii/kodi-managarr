import unittest
from datetime import datetime, timezone
from unittest import mock

from arr_manager.retention.config import RetentionSettings
from arr_manager.retention.enumerator import RetentionEnumerator


class Addon:
    def __init__(self, values=None): self.values = dict(values or {})
    def getSetting(self, key): return self.values.get(key, "")


class PathMapper:
    def kodi_to_remote(self, value): return value
    def remote_to_kodi(self, value): return value


class Kodi:
    def __init__(self, handler): self.handler = handler; self.calls = []
    def call(self, method, params):
        self.calls.append((method, params))
        return self.handler(method, params)


class Manager:
    def __init__(self):
        self.radarr = mock.MagicMock()
        self.sonarr = mock.MagicMock()


class RetentionEnumeratorTests(unittest.TestCase):
    def settings(self, movies=True, episodes=True):
        return RetentionSettings(Addon({
            "retention_enabled": "true",
            "retention_include_movies": str(movies).lower(),
            "retention_include_episodes": str(episodes).lower(),
        })).validate()

    def test_date_parsing_and_conservative_latest_added(self):
        parsed = RetentionEnumerator.parse_servarr_date("2020-01-01T12:00:00Z")
        self.assertEqual(parsed, datetime(2020, 1, 1, 12, tzinfo=timezone.utc).timestamp())
        self.assertIsNone(RetentionEnumerator.parse_servarr_date("bad"))
        self.assertEqual(RetentionEnumerator.conservative_added(100, None, 300, 200), 300)
        self.assertIsNone(RetentionEnumerator.conservative_added(None, 0))

    @mock.patch("arr_manager.retention.enumerator.resolve_movie")
    def test_movie_pages_are_bounded_and_streamed(self, resolve_movie):
        def handler(method, params):
            self.assertEqual(method, "VideoLibrary.GetMovies")
            start = params["limits"]["start"]
            if start == 0:
                rows = [
                    {
                        "movieid": index,
                        "title": f"Movie {index}",
                        "year": 2020,
                        "uniqueid": {"tmdb": str(index)},
                        "playcount": 1,
                        "lastplayed": "2020-01-01 12:00:00",
                        "dateadded": "2020-01-02 12:00:00",
                        "file": f"/movies/{index}.mkv",
                    }
                    for index in range(1, 201)
                ]
                return {"movies": rows, "limits": {"start": 0, "end": 200, "total": 201}}
            return {
                "movies": [{
                    "movieid": 201,
                    "title": "Movie 201",
                    "year": 2020,
                    "uniqueid": {"tmdb": "201"},
                    "playcount": 0,
                    "dateadded": "2020-01-02 12:00:00",
                    "file": "/movies/201.mkv",
                }],
                "limits": {"start": 200, "end": 201, "total": 201},
            }

        manager = Manager()
        manager.radarr.movie_files.side_effect = lambda movie_id: [{
            "id": movie_id + 1000,
            "dateAdded": "2020-01-03T12:00:00Z",
        }]
        resolve_movie.side_effect = lambda selected, _client, _mapper: {
            "id": selected.db_id,
            "title": selected.title,
            "added": "2020-01-01T12:00:00Z",
        }
        enumerator = RetentionEnumerator(Kodi(handler), manager, PathMapper())
        results = list(enumerator.iter_scan_results(self.settings(episodes=False)))
        candidates = [row.candidate for row in results if row.candidate]
        self.assertEqual(len(candidates), 201)
        self.assertTrue(candidates[0].watched)
        self.assertFalse(candidates[-1].watched)
        self.assertEqual(candidates[0].file_id, 1001)

    @mock.patch("arr_manager.retention.enumerator.resolve_episode_context")
    @mock.patch("arr_manager.retention.enumerator.resolve_series")
    def test_multi_episode_file_is_emitted_once_and_requires_all_rows_watched(
        self, resolve_series, resolve_context
    ):
        rows = [
            {"episodeid": 1, "title": "One", "season": 0, "episode": 1,
             "tvshowid": 9, "tvshowtitle": "Show", "playcount": 1,
             "lastplayed": "2020-01-04 12:00:00", "dateadded": "2020-01-01 12:00:00",
             "file": "/shows/a.mkv", "uniqueid": {"tvdb": "55"}},
            {"episodeid": 2, "title": "Two", "season": 0, "episode": 2,
             "tvshowid": 9, "tvshowtitle": "Show", "playcount": 0,
             "lastplayed": "", "dateadded": "2020-01-02 12:00:00",
             "file": "/shows/a.mkv", "uniqueid": {"tvdb": "55"}},
        ]

        def handler(method, params):
            if method == "VideoLibrary.GetTVShowDetails":
                return {"tvshowdetails": {"title": "Show", "year": 2020, "uniqueid": {"tvdb": "900"}}}
            self.assertEqual(method, "VideoLibrary.GetEpisodes")
            if params.get("tvshowid") == 9:
                return {"episodes": rows, "limits": {"start": 0, "end": 2, "total": 2}}
            return {"episodes": rows, "limits": {"start": 0, "end": 2, "total": 2}}

        resolve_series.return_value = {"id": 7, "title": "Show"}
        linked = [
            {"id": 101, "seasonNumber": 0, "episodeNumber": 1, "episodeFileId": 88},
            {"id": 102, "seasonNumber": 0, "episodeNumber": 2, "episodeFileId": 88},
        ]
        resolve_context.return_value = (linked[0], linked, {"id": 88, "dateAdded": "2020-01-03T12:00:00Z"})
        enumerator = RetentionEnumerator(Kodi(handler), Manager(), PathMapper())
        results = list(enumerator.iter_scan_results(self.settings(movies=False)))
        candidates = [row.candidate for row in results if row.candidate]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].kodi_db_ids, (1, 2))
        self.assertEqual(candidates[0].linked_episode_ids, (101, 102))
        self.assertFalse(candidates[0].watched)
        self.assertIn("S00E01", candidates[0].display_name)
        self.assertEqual(resolve_series.call_args[0][0].unique_ids, {"tvdb": "900"})

    @mock.patch("arr_manager.retention.enumerator.resolve_episode_context")
    @mock.patch("arr_manager.retention.enumerator.resolve_series")
    def test_episode_revalidation_refreshes_series_cache(self, resolve_series, resolve_context):
        detail = {
            "episodeid": 1, "title": "One", "season": 1, "episode": 1,
            "tvshowid": 9, "tvshowtitle": "Show", "playcount": 1,
            "lastplayed": "2020-01-04 12:00:00", "dateadded": "2020-01-01 12:00:00",
            "file": "/shows/a.mkv", "uniqueid": {"tvdb": "55"},
        }
        calls = {"series": 0}
        def handler(method, params):
            if method == "VideoLibrary.GetEpisodeDetails":
                return {"episodedetails": detail}
            if method == "VideoLibrary.GetTVShowDetails":
                return {"tvshowdetails": {"title": "Show", "year": 2020, "uniqueid": {"tvdb": "900"}}}
            if method == "VideoLibrary.GetEpisodes":
                calls["series"] += 1
                return {"episodes": [detail], "limits": {"start": 0, "end": 1, "total": 1}}
            raise AssertionError(method)
        resolve_series.return_value = {"id": 7, "title": "Show"}
        linked = [{"id": 101, "seasonNumber": 1, "episodeNumber": 1, "episodeFileId": 88}]
        resolve_context.return_value = (linked[0], linked, {"id": 88, "dateAdded": "2020-01-03T12:00:00Z"})
        enumerator = RetentionEnumerator(Kodi(handler), Manager(), PathMapper())
        first = enumerator._episode_candidate(detail)
        self.assertEqual(calls["series"], 1)
        fresh = enumerator.revalidate(first)
        self.assertEqual(calls["series"], 2)
        self.assertEqual(first.identity_tuple(), fresh.identity_tuple())


if __name__ == "__main__":
    unittest.main()
