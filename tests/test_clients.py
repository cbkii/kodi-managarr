import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.clients import RadarrClient, SonarrClient
from arr_manager.errors import ApiError


class HTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.responses.pop(0)


def client(kind, responses):
    value = object.__new__(kind)
    value.http = HTTP(responses)
    return value


class ClientTests(unittest.TestCase):
    def test_duplicate_external_id_rejected(self):
        radarr = client(RadarrClient, [[{"id": 1}, {"id": 2}]])
        with self.assertRaises(ApiError):
            radarr.movie_by_tmdb(5)

    def test_queue_and_remove_contracts(self):
        sonarr = client(SonarrClient, [{"records": [{"id": 9}]}, None])
        self.assertEqual(sonarr.queue(3), [{"id": 9}])
        sonarr.remove_queue_item(9)
        self.assertEqual(sonarr.http.calls[0][0], ("GET", "/queue"))
        self.assertEqual(sonarr.http.calls[1][0], ("DELETE", "/queue/9"))
        self.assertEqual(
            sonarr.http.calls[1][1]["params"],
            {"removeFromClient": True, "blocklist": False},
        )

    def test_radarr_destructive_and_command_contracts(self):
        radarr = client(
            RadarrClient,
            [None, None, [], {"records": []}, {"id": 101}, {"id": 102}, None],
        )

        radarr.delete_movie(4, delete_files=False, add_exclusion=True)
        radarr.delete_movie_file(7)
        self.assertEqual(radarr.movie_history(4), [])
        self.assertEqual(radarr.queue(4), [])
        self.assertEqual(radarr.search_movie(4)["id"], 101)
        self.assertEqual(radarr.rescan_movie(4)["id"], 102)
        radarr.mark_history_failed(33)

        self.assertEqual(radarr.http.calls, [
            (("DELETE", "/movie/4"), {"params": {"deleteFiles": False, "addImportExclusion": True}}),
            (("DELETE", "/movieFile/7"), {}),
            (("GET", "/history/movie"), {"params": {"movieId": 4, "eventType": 3}}),
            (("GET", "/queue"), {"params": {"page": 1, "pageSize": 100, "includeMovie": True, "movieIds": [4]}}),
            (("POST", "/command"), {"payload": {"name": "MoviesSearch", "movieIds": [4]}}),
            (("POST", "/command"), {"payload": {"name": "RescanMovie", "movieId": 4}}),
            (("POST", "/history/failed/33"), {"payload": {}}),
        ])

    def test_sonarr_destructive_and_command_contracts(self):
        sonarr = client(
            SonarrClient,
            [None, None, None, [], {"id": 201}, {"id": 202}, {"id": 203}, {}],
        )

        sonarr.delete_episode_file(8)
        sonarr.delete_episode_files([8, "9"])
        sonarr.delete_series(3, delete_files=False, add_exclusion=True)
        self.assertEqual(sonarr.series_history(3, season_number=0), [])
        self.assertEqual(sonarr.search_episodes([11, 12])["id"], 201)
        self.assertEqual(sonarr.search_series(3)["id"], 202)
        self.assertEqual(sonarr.rescan_series(3)["id"], 203)
        sonarr.set_episodes_monitored([1, 2], False)

        self.assertEqual(sonarr.http.calls, [
            (("DELETE", "/episodeFile/8"), {}),
            (("DELETE", "/episodeFile/bulk"), {"payload": {"episodeFileIds": [8, 9]}}),
            (("DELETE", "/series/3"), {"params": {"deleteFiles": False, "addImportListExclusion": True}}),
            (("GET", "/history/series"), {"params": {"seriesId": 3, "seasonNumber": 0, "eventType": 3}}),
            (("POST", "/command"), {"payload": {"name": "EpisodeSearch", "episodeIds": [11, 12]}}),
            (("POST", "/command"), {"payload": {"name": "SeriesSearch", "seriesId": 3}}),
            (("POST", "/command"), {"payload": {"name": "RescanSeries", "seriesId": 3}}),
            (("PUT", "/episode/monitor"), {"payload": {"episodeIds": [1, 2], "monitored": False}}),
        ])

    def test_invalid_ids_fail_before_http_mutation(self):
        radarr = client(RadarrClient, [])
        sonarr = client(SonarrClient, [])
        for operation in (
            lambda: radarr.delete_movie_file(0),
            lambda: radarr.search_movie(-1),
            lambda: sonarr.delete_episode_files([1, 0]),
            lambda: sonarr.delete_series("not-an-id"),
            lambda: sonarr.set_episodes_monitored([1, 0], False),
        ):
            with self.subTest(operation=operation), self.assertRaises(ApiError):
                operation()
        self.assertEqual(radarr.http.calls, [])
        self.assertEqual(sonarr.http.calls, [])
        sonarr.set_episodes_monitored([], False)
        self.assertEqual(sonarr.http.calls, [])


if __name__ == "__main__":
    unittest.main()
