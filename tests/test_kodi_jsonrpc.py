import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.kodi import KodiJsonRpcClient, KodiJsonRpcError


class Xbmc:
    def __init__(self, response):
        self.response = response
        self.requests = []
    def executeJSONRPC(self, payload):
        self.requests.append(json.loads(payload))
        return self.response


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


if __name__ == "__main__":
    unittest.main()
