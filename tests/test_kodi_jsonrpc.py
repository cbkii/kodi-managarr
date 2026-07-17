import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))
from arr_manager.kodi import KodiJsonRpcClient, KodiJsonRpcError, KodiUI
from arr_manager.models import SelectedItem


class Xbmc:
    def __init__(self, *responses): self.responses = list(responses); self.requests = []
    def executeJSONRPC(self, payload): self.requests.append(json.loads(payload)); return self.responses.pop(0)

def result(request_id, value): return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": value})


class JsonRpcTests(unittest.TestCase):
    def test_remove_movie_uses_targeted_method(self):
        xbmc = Xbmc(result(1, "OK")); client = KodiJsonRpcClient(xbmc)
        self.assertEqual(client.remove_movie(12), "OK")
        self.assertEqual(xbmc.requests[0]["method"], "VideoLibrary.RemoveMovie")
        self.assertEqual(xbmc.requests[0]["params"], {"movieid": 12})

    def test_malformed_and_mismatched_responses_rejected(self):
        for raw in ("not-json", "[]", '"string"', "null"):
            with self.subTest(raw=raw), self.assertRaises(KodiJsonRpcError):
                KodiJsonRpcClient(Xbmc(raw)).remove_movie(1)
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc(json.dumps({"jsonrpc": "2.0", "id": 99, "result": "OK"}))).remove_movie(1)

    def test_episode_sync_resolves_selected_and_linked_rows(self):
        path = "/shows/Show/S01E02-E03.mkv"
        xbmc = Xbmc(
            result(1, {"episodedetails": {"episodeid": 10, "tvshowid": 7, "season": 1, "episode": 2, "file": path, "tvshowtitle": "Show"}}),
            result(2, {"episodes": [
                {"episodeid": 10, "tvshowid": 7, "season": 1, "episode": 2, "file": path},
                {"episodeid": 11, "tvshowid": 7, "season": 1, "episode": 3, "file": path},
            ]}), result(3, "OK"), result(4, "OK"),
        )
        ui = object.__new__(KodiUI); ui.jsonrpc = KodiJsonRpcClient(xbmc)
        selected = SelectedItem(media_type="episode", db_id=10, tvshow_title="Show", season=1, episode=2, file_path=path)
        synced = KodiUI.sync_deleted_episodes(ui, selected, [{"seasonNumber": 1, "episodeNumber": 2}, {"seasonNumber": 1, "episodeNumber": 3}])
        self.assertEqual([item["id"] for item in synced["removed"]], [10, 11])

    def test_sync_plan_does_not_remove_rows_until_applied(self):
        xbmc = Xbmc(
            result(1, {"moviedetails": {"movieid": 12, "title": "Film", "year": 2024, "file": "/movies/Film.mkv", "uniqueid": {"tmdb": "1"}}}),
            result(2, "OK"),
        )
        ui = object.__new__(KodiUI); ui.jsonrpc = KodiJsonRpcClient(xbmc)
        selected = SelectedItem(media_type="movie", db_id=12, title="Film", year=2024, file_path="/movies/Film.mkv", unique_ids={"tmdb": "1"})
        plan = KodiUI.plan_deleted_movie(ui, selected)
        self.assertEqual(plan, {"status": "planned", "kind": "movie", "id": 12})
        self.assertEqual([request["method"] for request in xbmc.requests], ["VideoLibrary.GetMovieDetails"])
        result_value = KodiUI.apply_sync_plan(ui, plan)
        self.assertEqual(result_value["status"], "removed")
        self.assertEqual([request["method"] for request in xbmc.requests][-1], "VideoLibrary.RemoveMovie")

    def test_series_replacement_does_not_remove_tvshow(self):
        xbmc = Xbmc(
            result(1, {"tvshowdetails": {"tvshowid": 7, "title": "Show", "year": 2020, "uniqueid": {"tvdb": "77"}}}),
            result(2, {"episodes": [{"episodeid": 10, "season": 1, "episode": 1, "tvshowid": 7, "file": "/shows/1.mkv"}]}),
            result(3, "OK"),
        )
        ui = object.__new__(KodiUI); ui.jsonrpc = KodiJsonRpcClient(xbmc)
        selected = SelectedItem(media_type="tvshow", db_id=7, title="Show", year=2020, unique_ids={"tvdb": "77"})
        KodiUI.sync_deleted_episodes(ui, selected, [{"seasonNumber": 1, "episodeNumber": 1}])
        methods = [request["method"] for request in xbmc.requests]
        self.assertIn("VideoLibrary.RemoveEpisode", methods)
        self.assertNotIn("VideoLibrary.RemoveTVShow", methods)


if __name__ == "__main__": unittest.main()
