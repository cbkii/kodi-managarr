import json
import os
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import SafetyError
from arr_manager.subtitle_service import (
    SubtitleService, _language_code, _result_label, _safe_result, _select_results,
)


class FakeVfs:
    def __init__(self, profile): self.profile = profile; self.files = set()
    def translatePath(self, value): return self.profile
    def listdir(self, directory): return [], [os.path.basename(value) for value in self.files if os.path.dirname(value) == directory]
    def exists(self, path): return path in self.files


class Addon:
    def getLocalizedString(self, value): return ""


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

    def test_safe_result_keeps_only_exact_download_identity(self):
        result = _safe_result({
            "language": "en", "provider": "p", "subtitle": "opaque-token", "score": 99,
            "release_info": ["title"], "secret": "x", "forced": True,
        })
        self.assertEqual(result["provider"], "p")
        self.assertEqual(result["subtitle"], "opaque-token")
        self.assertTrue(result["forced"])
        self.assertNotIn("language", result)
        self.assertNotIn("score", result)
        self.assertNotIn("release_info", result)
        self.assertNotIn("secret", result)

    def test_safe_result_rejects_url_or_missing_download_identity(self):
        with self.assertRaises(SafetyError):
            _safe_result({"provider": "p", "subtitle": "https://provider.example/token"})
        with self.assertRaises(SafetyError):
            _safe_result({"provider": "p"})

    def test_language_filter_keeps_forced_and_hi_variants_in_configured_order(self):
        rows = [
            {"language": "fr", "provider": "p", "score": 60},
            {"language": "en", "provider": "p", "score": 40, "forced": True},
            {"language": "en", "provider": "p", "score": 80, "forced": True},
            {"language": "en", "provider": "p", "score": 70, "hi": True},
            {"language": "de", "provider": "p", "score": 100},
        ]
        selected = _select_results(rows, ["en", "fr"])
        self.assertEqual([language for language, _ in selected], ["en:forced", "en:hi", "fr"])
        self.assertEqual(selected[0][1]["score"], 80)

    def test_result_label_uses_provider_score_release_match_and_flags(self):
        label, detail = _result_label(
            Addon(),
            {
                "provider": "OpenSubtitles", "score": 91.5, "release_info": ["title", "season"],
                "forced": True,
            },
            "en:forced",
        )
        self.assertEqual(label, "en:forced")
        self.assertIn("OpenSubtitles", detail)
        self.assertIn("score 91.5", detail)
        self.assertIn("match title, season", detail)
        self.assertIn("forced", detail)

    def test_cache_rejects_invalid_and_expired_tokens(self):
        with tempfile.TemporaryDirectory() as profile:
            service = self.make_service(profile)
            with self.assertRaises(SafetyError): service._load_cache("../bad")
            token = service._save_cache({"language": "en"})
            path = os.path.join(profile, f"subtitle-{token}.json")
            os.utime(path, (time.time() - 2000, time.time() - 2000))
            with self.assertRaises(SafetyError): service._load_cache(token)

    def test_cache_contains_no_media_path_and_uses_private_permissions(self):
        with tempfile.TemporaryDirectory() as profile:
            service = self.make_service(profile)
            payload = {
                "media_type": "movie", "kodi_db_id": 7, "radarr_id": 9, "language": "en",
                "result": {"provider": "p", "subtitle": "opaque", "forced": False},
                "created": int(time.time()),
            }
            token = service._save_cache(payload)
            path = os.path.join(profile, f"subtitle-{token}.json")
            stored = json.loads(open(path, encoding="utf-8").read())
            self.assertNotIn("playing_file", stored)
            self.assertNotIn("url", json.dumps(stored).lower())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

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
