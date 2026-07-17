import io
import os
import sys
import unittest
from urllib.request import Request
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import ApiError
from arr_manager.http import JsonHttpClient, MAX_RESPONSE_BYTES, _SameOriginRedirectHandler


class Response:
    def __init__(self, body=b'{"ok":true}', content_type="application/json"):
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n=-1): return self.body if n < 0 else self.body[:n]


class Opener:
    def __init__(self, response): self.response = response
    def open(self, *args, **kwargs): return self.response


class HttpTests(unittest.TestCase):
    def test_rejects_query_fragment_credentials_and_bad_version(self):
        for value in ("http://user:pass@host", "http://host/?x=1", "http://host/#x", "ftp://host"):
            with self.subTest(value=value), self.assertRaises(ApiError):
                JsonHttpClient(value, "key")
        with self.assertRaises(ApiError):
            JsonHttpClient("http://host", "key", "../v3")

    def test_parses_json_and_accepts_empty_response(self):
        with patch("arr_manager.http.build_opener", return_value=Opener(Response())):
            self.assertEqual(JsonHttpClient("http://host", "key").request("GET", "/x"), {"ok": True})
        with patch("arr_manager.http.build_opener", return_value=Opener(Response(b""))):
            self.assertIsNone(JsonHttpClient("http://host", "key").request("DELETE", "/x"))

    def test_bounded_response_and_truncated_error_reader(self):
        with patch("arr_manager.http.build_opener", return_value=Opener(Response(b"x" * (MAX_RESPONSE_BYTES + 1)))):
            with self.assertRaises(ApiError):
                JsonHttpClient("http://host", "key").request("GET", "/x")
        self.assertEqual(JsonHttpClient._read_bounded(io.BytesIO(b"abcdef"), 3, truncate=True), b"abc")

    def test_cross_origin_redirect_is_rejected_before_credentials_are_forwarded(self):
        request = Request("https://servarr.local/api/v3/system/status", headers={"X-Api-Key": "secret"})
        with self.assertRaises(ApiError):
            _SameOriginRedirectHandler().redirect_request(
                request, None, 302, "Found", {}, "https://other.local/api/v3/system/status"
            )


if __name__ == "__main__":
    unittest.main()
