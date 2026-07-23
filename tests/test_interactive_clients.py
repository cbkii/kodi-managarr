import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.bazarr_client import BazarrClient
from arr_manager.clients import ProwlarrClient, RadarrClient, SonarrClient


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

    def test_bazarr_uses_unversioned_api_and_exact_provider_downloads(self):
        with mock.patch("arr_manager.bazarr_client.JsonHttpClient") as http_type:
            http = http_type.return_value
            http.base_url = "http://bazarr"
            client = BazarrClient("http://bazarr", "key")
        client.http = http
        self.assertEqual(client.http.api_root, "http://bazarr/api")
        http.request.side_effect = [{"data": []}, {"data": []}, {"data": []}, None, None]
        client.languages()
        client.search_movie_subtitles(7)
        client.search_episode_subtitles(8)
        selected = {"provider": "opensubtitles", "subtitle": "opaque", "original_format": True, "forced": True}
        client.download_movie_subtitle(7, "en:forced", selected)
        selected_episode = {"provider": "provider", "subtitle": "opaque2", "hi": True}
        client.download_episode_subtitle(9, 8, "en:hi", selected_episode)
        self.assertEqual(http.request.call_args_list[0], mock.call("GET", "/system/languages"))
        self.assertEqual(http.request.call_args_list[1], mock.call("GET", "/providers/movies", params={"radarrid": 7}))
        movie_params = http.request.call_args_list[3].kwargs["params"]
        self.assertEqual(movie_params, {
            "hi": False, "forced": True, "original_format": True,
            "provider": "opensubtitles", "subtitle": "opaque", "radarrid": 7,
        })
        self.assertEqual(http.request.call_args_list[3].args[:2], ("POST", "/providers/movies"))
        episode_params = http.request.call_args_list[4].kwargs["params"]
        self.assertEqual(episode_params, {
            "hi": True, "forced": False, "original_format": False,
            "provider": "provider", "subtitle": "opaque2", "seriesid": 9, "episodeid": 8,
        })
        self.assertEqual(http.request.call_args_list[4].args[:2], ("POST", "/providers/episodes"))


if __name__ == "__main__":
    unittest.main()
