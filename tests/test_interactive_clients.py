import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.clients import BazarrClient, ProwlarrClient, RadarrClient, SonarrClient


class InteractiveClientContractTests(unittest.TestCase):
    def client(self, cls):
        with mock.patch("arr_manager.clients.JsonHttpClient") as http_type:
            http = http_type.return_value
            client = cls("http://service", "key")
        client.http = http
        return client, http

    def test_radarr_lookup_add_release_and_dashboard_contracts(self):
        client, http = self.client(RadarrClient)
        http.request.side_effect = [[], {"id": 1}, [], {"id": 2}, [], [], {}, {}]
        self.assertEqual(client.lookup_movie("tmdb:42"), [])
        client.add_movie({"title": "Film"})
        client.releases(1)
        client.download_release({"guid": "g"})
        client.health(); client.root_folders(); client.wanted_missing(); client.queue_overview()
        self.assertEqual(http.request.call_args_list[0], mock.call("GET", "/movie/lookup", params={"term": "tmdb:42"}))
        self.assertEqual(http.request.call_args_list[1], mock.call("POST", "/movie", payload={"title": "Film"}))
        self.assertEqual(http.request.call_args_list[2], mock.call("GET", "/release", params={"movieId": 1}))
        self.assertEqual(http.request.call_args_list[3], mock.call("POST", "/release", payload={"guid": "g"}))

    def test_sonarr_lookup_add_and_episode_release_contracts(self):
        client, http = self.client(SonarrClient)
        http.request.side_effect = [[], {"id": 1}, [], {"id": 2}]
        client.lookup_series("tvdb:99")
        client.add_series({"title": "Show"})
        client.releases(44)
        client.download_release({"guid": "g"})
        self.assertEqual(http.request.call_args_list[0], mock.call("GET", "/series/lookup", params={"term": "tvdb:99"}))
        self.assertEqual(http.request.call_args_list[2], mock.call("GET", "/release", params={"episodeId": 44}))

    def test_prowlarr_is_a_narrow_independent_client(self):
        client, http = self.client(ProwlarrClient)
        http.request.side_effect = [{"version": "1"}, [], [], {"data": []}]
        client.status(); client.health(); client.indexers(); client.search("Film")
        self.assertFalse(hasattr(client, "delete_movie"))
        self.assertFalse(hasattr(client, "download_release"))
        self.assertEqual(http.request.call_args_list[-1], mock.call("GET", "/search", params={"query": "Film"}))

    def test_bazarr_uses_unversioned_api_and_verified_resources(self):
        with mock.patch("arr_manager.clients.JsonHttpClient") as http_type:
            http = http_type.return_value
            http.base_url = "http://bazarr"
            client = BazarrClient("http://bazarr", "key")
        client.http = http
        self.assertEqual(client.http.api_root, "http://bazarr/api")
        http.request.side_effect = [{"data": []}, {"data": []}, {"data": []}, None, None]
        client.languages()
        client.search_movie_subtitles(7)
        client.search_episode_subtitles(8)
        client.download_movie_subtitle(7, "en:forced", {"forced": True})
        client.download_episode_subtitle(9, 8, "en:hi", {"hi": True})
        self.assertEqual(http.request.call_args_list[0], mock.call("GET", "/system/languages"))
        self.assertEqual(http.request.call_args_list[1], mock.call("GET", "/providers/movies", params={"radarrid": 7}))
        movie_params = http.request.call_args_list[3].kwargs["params"]
        self.assertEqual(movie_params, {"language": "en", "forced": True, "hi": False, "radarrid": 7})
        episode_params = http.request.call_args_list[4].kwargs["params"]
        self.assertEqual(episode_params, {"language": "en", "forced": False, "hi": True, "seriesid": 9, "episodeid": 8})


if __name__ == "__main__":
    unittest.main()
