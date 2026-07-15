import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import ApiError
from arr_manager.http import JsonHttpClient

class Response:
    def __init__(self, body=b'{"ok": true}', content_type="application/json"):
        self.body = body
        self.headers = {"Content-Type": content_type}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.body

class HttpTests(unittest.TestCase):
    def test_rejects_malformed_base_url_and_api_version(self):
        with self.assertRaises(ApiError):
            JsonHttpClient("not-a-url", "key")
        with self.assertRaises(ApiError):
            JsonHttpClient("http://user:pass@host", "key")
        with self.assertRaises(ApiError):
            JsonHttpClient("http://host", "key", "../v3")

    def test_redacts_logged_urls_and_parses_json(self):
        logs = []
        logger = type("L", (), {"debug": lambda self, *args: logs.append(args)})()
        client = JsonHttpClient("http://host/base", "secret", logger=logger)
        with patch("arr_manager.http.urlopen", return_value=Response()):
            self.assertEqual(client.request("GET", "/system/status"), {"ok": True})
        self.assertNotIn("secret", str(logs))

    def test_rejects_unexpected_content_type_and_invalid_json(self):
        client = JsonHttpClient("http://host", "key")
        with patch("arr_manager.http.urlopen", return_value=Response(b"html", "text/html")):
            with self.assertRaises(ApiError):
                client.request("GET", "/x")
        with patch("arr_manager.http.urlopen", return_value=Response(b"not-json", "application/json")):
            with self.assertRaises(ApiError):
                client.request("GET", "/x")

if __name__ == "__main__":
    unittest.main()
