import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.kodi import KodiJsonRpcClient, KodiJsonRpcError
from arr_manager.models import SelectedItem


class Xbmc:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
    def executeJSONRPC(self, payload):
        self.requests.append(json.loads(payload))
        return self.responses.pop(0)


class JsonRpcTests(unittest.TestCase):
    def test_remove_movie_uses_targeted_video_library_method(self):
        xbmc = Xbmc(json.dumps({"jsonrpc": "2.0", "id": 1, "result": "OK"}))
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

    def test_episode_sync_removes_selected_and_linked_kodi_rows_once(self):
        from arr_manager.kodi import KodiUI
        ui = object.__new__(KodiUI)
        xbmc = Xbmc(
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": "OK"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": "OK"}),
        )
        ui.jsonrpc = KodiJsonRpcClient(xbmc)
        result = KodiUI.sync_deleted_episodes(ui, SelectedItem(media_type="episode", db_id=10), [
            {"kodiDbId": 10}, {"kodiEpisodeId": 11}, {"id": 5}
        ])
        self.assertEqual(result, ["OK", "OK"])
        self.assertEqual([req["params"] for req in xbmc.requests], [{"episodeid": 10}, {"episodeid": 11}])

if __name__ == "__main__":
    unittest.main()
