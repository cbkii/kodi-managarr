import os
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import SafetyError
from arr_manager.subtitle_service import SubtitleService, _language_code, _safe_result


class FakeVfs:
    def __init__(self, profile): self.profile = profile; self.files = set()
    def translatePath(self, value): return self.profile
    def listdir(self, directory): return [], [os.path.basename(value) for value in self.files if os.path.dirname(value) == directory]
    def exists(self, path): return path in self.files


class SubtitleServiceTests(unittest.TestCase):
    def make_service(self, profile):
        addon = mock.MagicMock(); addon.getAddonInfo.return_value = profile
        settings = mock.MagicMock(); settings.path_mapper.remote_to_kodi.return_value = ""
        ui = mock.MagicMock(); ui.wait_for_abort.return_value = False
        service = SubtitleService.__new__(SubtitleService)
        service.addon = addon; service.settings = settings; service.ui = ui; service.logger = mock.MagicMock()
        service.profile = profile; service.xbmcvfs = FakeVfs(profile)
        return service

    def test_language_normalisation_accepts_nested_bazarr_shape(self):
        self.assertEqual(_language_code({"language": {"code2": "EN"}}), "en")
        self.assertEqual(_language_code({"code3": "ind"}), "ind")

    def test_safe_result_drops_unknown_and_sensitive_fields(self):
        result = _safe_result({"language": "en", "provider": "p", "secret": "x", "subtitle": "token"})
        self.assertEqual(result["language"], "en")
        self.assertNotIn("secret", result)

    def test_cache_rejects_invalid_and_expired_tokens(self):
        with tempfile.TemporaryDirectory() as profile:
            service = self.make_service(profile)
            with self.assertRaises(SafetyError): service._load_cache("../bad")
            token = service._save_cache({"language": "en"})
            path = os.path.join(profile, f"subtitle-{token}.json")
            os.utime(path, (time.time() - 2000, time.time() - 2000))
            with self.assertRaises(SafetyError): service._load_cache(token)

    def test_candidate_scan_returns_only_matching_language_and_media_stem(self):
        with tempfile.TemporaryDirectory() as profile:
            service = self.make_service(profile)
            service.xbmcvfs.files = {
                "/media/Film.en.srt", "/media/Film.fr.srt", "/media/Other.en.srt", "/media/Film.en.txt",
            }
            self.assertEqual(service._subtitle_candidates("/media/Film.mkv", "en"), ["/media/Film.en.srt"])

    def test_response_server_path_requires_accessible_mapping(self):
        with tempfile.TemporaryDirectory() as profile:
            service = self.make_service(profile)
            service.settings.path_mapper.remote_to_kodi.return_value = "smb://server/subs/Film.en.srt"
            service.xbmcvfs.files.add("smb://server/subs/Film.en.srt")
            self.assertEqual(service._map_accessible_path("/srv/subs/Film.en.srt"), "smb://server/subs/Film.en.srt")


if __name__ == "__main__":
    unittest.main()
