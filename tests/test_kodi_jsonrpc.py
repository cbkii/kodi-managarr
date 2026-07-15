import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.kodi import KodiJsonRpcClient, KodiJsonRpcError, KodiUI
from arr_manager.models import SelectedItem


class Xbmc:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def executeJSONRPC(self, payload):
        self.requests.append(json.loads(payload))
        return self.responses.pop(0)


def result(request_id, value):
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": value})


class JsonRpcTests(unittest.TestCase):
    def test_remove_movie_uses_targeted_video_library_method(self):
        xbmc = Xbmc(result(1, "OK"))
        client = KodiJsonRpcClient(xbmc)
        self.assertEqual(client.remove_movie(12), "OK")
        self.assertEqual(xbmc.requests[0]["method"], "VideoLibrary.RemoveMovie")
        self.assertEqual(xbmc.requests[0]["params"], {"movieid": 12})

    def test_jsonrpc_error_is_raised(self):
        xbmc = Xbmc(json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "bad"}}))
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(xbmc).remove_episode(4)

    def test_malformed_json_is_raised(self):
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc("not-json")).remove_tvshow(3)

    def test_non_object_jsonrpc_responses_are_rejected(self):
        for raw in ("[]", '"string"', "12", "null"):
            with self.subTest(raw=raw):
                with self.assertRaises(KodiJsonRpcError):
                    KodiJsonRpcClient(Xbmc(raw)).remove_movie(1)

    def test_mismatched_id_and_missing_result_are_rejected(self):
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc(json.dumps({"jsonrpc": "2.0", "id": 99, "result": "OK"}))).remove_movie(1)
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc(json.dumps({"jsonrpc": "2.0", "id": 1}))).remove_movie(1)

    def test_malformed_error_is_rejected(self):
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc(json.dumps({"jsonrpc": "2.0", "id": 1, "error": "bad"}))).remove_movie(1)

    def test_malformed_result_shapes_are_rejected(self):
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc(result(1, {"moviedetails": []}))).movie_details(1)
        with self.assertRaises(KodiJsonRpcError):
            KodiJsonRpcClient(Xbmc(result(1, {"episodes": {}}))).episodes(1)

    def test_episode_sync_resolves_selected_and_linked_rows(self):
        path = "/shows/Show/S01E02-E03.mkv"
        xbmc = Xbmc(
            result(1, {"episodedetails": {"episodeid": 10, "tvshowid": 7, "season": 1,
                "episode": 2, "file": path, "tvshowtitle": "Show"}}),
            result(2, {"episodes": [
                {"episodeid": 10, "tvshowid": 7, "season": 1, "episode": 2, "file": path},
                {"episodeid": 11, "tvshowid": 7, "season": 1, "episode": 3, "file": path},
            ]}),
            result(3, "OK"),
            result(4, "OK"),
        )
        ui = object.__new__(KodiUI)
        ui.jsonrpc = KodiJsonRpcClient(xbmc)
        selected = SelectedItem(media_type="episode", db_id=10, tvshow_title="Show",
            season=1, episode=2, file_path=path)
        linked = [{"seasonNumber": 1, "episodeNumber": 2},
                  {"seasonNumber": 1, "episodeNumber": 3}]
        synced = KodiUI.sync_deleted_episodes(ui, selected, linked)
        self.assertEqual([item["id"] for item in synced["removed"]], [10, 11])
        self.assertEqual([req["method"] for req in xbmc.requests][-2:],
            ["VideoLibrary.RemoveEpisode", "VideoLibrary.RemoveEpisode"])

    def test_series_replacement_removes_episodes_not_tvshow(self):
        xbmc = Xbmc(
            result(1, {"tvshowdetails": {"tvshowid": 7, "title": "Show", "year": 2020,
                "uniqueid": {"tvdb": "77"}}}),
            result(2, {"episodes": [{"episodeid": 10, "season": 1, "episode": 1,
                "tvshowid": 7, "file": "/shows/1.mkv"}]}),
            result(3, "OK"),
        )
        ui = object.__new__(KodiUI)
        ui.jsonrpc = KodiJsonRpcClient(xbmc)
        selected = SelectedItem(media_type="tvshow", db_id=7, title="Show", year=2020,
            unique_ids={"tvdb": "77"})
        synced = KodiUI.sync_deleted_episodes(ui, selected,
            [{"seasonNumber": 1, "episodeNumber": 1}])
        self.assertEqual(synced["status"], "removed")
        methods = [req["method"] for req in xbmc.requests]
        self.assertIn("VideoLibrary.RemoveEpisode", methods)
        self.assertNotIn("VideoLibrary.RemoveTVShow", methods)


if __name__ == "__main__":
    unittest.main()
