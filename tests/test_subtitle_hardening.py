import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.bazarr_client import BazarrApiError, BazarrClient
from arr_manager.diagnostics_hardening import bazarr_diagnostics
from arr_manager.errors import ApiError, SafetyError
from arr_manager.models import SelectedItem
import arr_manager.subtitle_service as subtitle_module
from arr_manager.subtitle_hardening import install as install_subtitle_hardening

install_subtitle_hardening(subtitle_module)

from arr_manager.subtitle_service import (
    SubtitleService,
    _flag,
    _safe_result,
    _select_results,
    selected_from_player,
)


class FakeHttp:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def request(self, method, path, params=None):
        self.calls.append((method, path, params))
        if self.error:
            raise self.error
        return self.response


def client(response=None, error=None):
    value = object.__new__(BazarrClient)
    value.http = FakeHttp(response, error)
    value.last_operation = ""
    value.last_category = ""
    value.last_status = None
    return value


class BazarrContractTests(unittest.TestCase):
    def test_string_false_flags_remain_false(self):
        self.assertFalse(_flag("False"))
        self.assertFalse(_flag("0"))
        self.assertTrue(_flag("true"))
        self.assertEqual(
            _safe_result({"provider": "p", "subtitle": "s", "forced": "False", "hearing_impaired": "False"}),
            {"provider": "p", "subtitle": "s", "original_format": False, "forced": False,
             "hearing_impaired": False, "hi": False},
        )

    def test_download_parameters_match_official_provider_contract(self):
        value = client(None)
        value.download_movie_subtitle(12, "en", {
            "provider": "opensubtitlescom", "subtitle": "opaque-id",
            "hi": "False", "forced": "False", "original_format": "True",
        })
        method, path, params = value.http.calls[-1]
        self.assertEqual((method, path), ("POST", "/providers/movies"))
        self.assertEqual(params["radarrid"], 12)
        self.assertFalse(params["hi"])
        self.assertFalse(params["forced"])
        self.assertTrue(params["original_format"])

    def test_episode_download_uses_series_and_episode_ids(self):
        value = client(None)
        value.download_episode_subtitle(4, 8, "en:forced", {"provider": "p", "subtitle": "s"})
        _, path, params = value.http.calls[-1]
        self.assertEqual(path, "/providers/episodes")
        self.assertEqual((params["seriesid"], params["episodeid"]), (4, 8))
        self.assertTrue(params["forced"])

    def test_status_unwraps_data_envelope(self):
        value = client({"data": {"bazarr_version": "1.5.6"}})
        self.assertEqual(value.status()["bazarr_version"], "1.5.6")


    def test_missing_status_version_is_unsupported_contract(self):
        value = client({"data": {"package_version": "x"}})
        with self.assertRaises(BazarrApiError) as raised:
            value.status()
        self.assertEqual(raised.exception.category, "unsupported_contract")

    def test_error_is_operation_classified_without_url(self):
        value = client(error=ApiError("API request failed with HTTP 401: secret", status=401))
        with self.assertRaises(BazarrApiError) as raised:
            value.search_movie_subtitles(3)
        self.assertEqual(raised.exception.category, "authentication")
        self.assertEqual(raised.exception.status, 401)
        self.assertNotIn("secret", str(raised.exception).lower())


class SubtitleFilteringTests(unittest.TestCase):
    def test_results_are_ordered_bounded_and_qualifier_aware(self):
        rows = [
            {"language": "fr", "provider": "p", "subtitle": "fr", "score": 1},
            {"language": "en", "provider": "p", "subtitle": "en-hi", "score": 99, "hearing_impaired": "True"},
            {"language": "en", "provider": "p", "subtitle": "en", "score": 80, "hearing_impaired": "False"},
            {"language": "de", "provider": "p", "subtitle": "de", "score": 2},
        ]
        result = _select_results(rows, ["en", "fr", "de"])
        self.assertEqual([language for language, _ in result], ["en", "en:hi", "fr"])
        self.assertEqual(len(result), 3)

    def test_canonical_showtitle_wins_for_playing_episode(self):
        class Xbmc:
            @staticmethod
            def getInfoLabel(name):
                return {"VideoPlayer.DBTYPE": "episode", "VideoPlayer.DBID": "7"}.get(name, "")

            class Player:
                def getPlayingFile(self):
                    return "smb://server/show/e.mkv"

        kodi = SimpleNamespace(
            episode_details=lambda _: {"title": "Ep", "showtitle": "Canonical", "tvshowtitle": "Legacy",
                                       "tvshowid": 2, "season": 0, "episode": 1, "file": "", "uniqueid": {}},
            tvshow_details=lambda _: {"title": "Series", "year": 2026, "uniqueid": {}},
        )
        selected = selected_from_player(SimpleNamespace(), Xbmc, kodi)
        self.assertEqual(selected.tvshow_title, "Canonical")
        self.assertEqual(selected.season, 0)


class DeliverySafetyTests(unittest.TestCase):
    def service(self):
        value = object.__new__(SubtitleService)
        value.addon = SimpleNamespace(getLocalizedString=lambda _: "")
        value.settings = SimpleNamespace(path_mapper=SimpleNamespace(remote_to_kodi=lambda _: "smb://server/mapped.srt"))
        value.xbmcvfs = SimpleNamespace(exists=lambda path: path.startswith("smb://"))
        return value

    def test_server_path_is_never_returned_when_only_mapping_is_accessible(self):
        value = self.service()
        self.assertEqual(value._map_accessible_path("/srv/media/file.en.srt"), "smb://server/mapped.srt")

    def test_unmapped_server_path_is_rejected(self):
        value = self.service()
        value.settings.path_mapper.remote_to_kodi = lambda _: ""
        value.xbmcvfs.exists = lambda _: False
        self.assertEqual(value._map_accessible_path("/srv/media/file.en.srt"), "")

    def test_smb_sidecar_detection(self):
        value = self.service()
        value.xbmcvfs = SimpleNamespace(
            listdir=lambda _: ([], ["Episode.mkv", "Episode.en.srt", "Other.en.srt"]),
            exists=lambda _: True,
        )
        rows = value._subtitle_candidates("smb://server/show/Episode.mkv", "en")
        self.assertEqual(rows, ["smb://server/show/Episode.en.srt"])

    def test_single_use_token_rejects_replay(self):
        value = self.service()
        value.profile = tempfile.mkdtemp()
        token = "a" * 32
        payload = {
            "created": int(time.time()), "media_type": "movie", "kodi_db_id": 1, "radarr_id": 2,
            "language": "en", "result": {"provider": "p", "subtitle": "s", "original_format": False,
                                                   "forced": False, "hearing_impaired": False, "hi": False},
        }
        with open(os.path.join(value.profile, f"subtitle-{token}.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self.assertEqual(value._consume_cache(token), payload)
        with self.assertRaises(SafetyError):
            value._consume_cache(token)


class ProviderBootstrapTests(unittest.TestCase):
    @staticmethod
    def load_module():
        spec = importlib.util.spec_from_file_location("subtitle_entry_test", os.path.join(ROOT, "subtitles.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_query_can_come_from_plugin_url(self):
        module = self.load_module()
        self.assertEqual(module._query_params(["plugin://x/?action=download&token=abc", "5"])["token"], "abc")

    def test_failure_completes_failed_directory(self):
        module = self.load_module()
        ended = []
        plugin = SimpleNamespace(
            addDirectoryItem=lambda *args, **kwargs: None,
            endOfDirectory=lambda handle, **kwargs: ended.append((handle, kwargs)),
        )
        class AddonModule:
            @staticmethod
            def Addon(id=None):
                return SimpleNamespace()
        class Ui:
            jsonrpc = object()
            def __init__(self, addon): pass
            def notification(self, *args, **kwargs): pass
        class Service:
            def __init__(self, *args): pass
            def search(self, base): raise RuntimeError("boom")
        module.xbmcaddon = AddonModule
        module.xbmcgui = SimpleNamespace(ListItem=lambda **kwargs: SimpleNamespace(setPath=lambda _: None))
        module.xbmcplugin = plugin
        module.xbmcvfs = SimpleNamespace()
        module.Settings = lambda addon: SimpleNamespace(debug=False)
        module.imessage = lambda addon, key, **values: key
        module.KodiLogger = lambda debug: SimpleNamespace(debug_enabled=False, error=lambda *args: None)
        module.KodiUI = Ui
        module.SubtitleService = Service
        self.assertFalse(module.main(["plugin://x", "5", "?action=search"]))
        self.assertEqual(ended, [(5, {"succeeded": False, "cacheToDisc": False})])

    def test_unknown_action_completes_failed_directory(self):
        module = self.load_module()
        ended = []
        plugin = SimpleNamespace(addDirectoryItem=lambda *a, **k: None,
                                 endOfDirectory=lambda h, **k: ended.append((h, k)))
        module.xbmcaddon = SimpleNamespace(Addon=lambda id=None: SimpleNamespace())
        module.xbmcgui = SimpleNamespace(ListItem=lambda **kwargs: SimpleNamespace(setPath=lambda _: None))
        module.xbmcplugin = plugin
        module.xbmcvfs = SimpleNamespace()
        module.Settings = lambda addon: SimpleNamespace(debug=False)
        module.imessage = lambda addon, key, **values: key
        module.KodiLogger = lambda debug: SimpleNamespace(debug_enabled=False, error=lambda *args: None)
        module.KodiUI = lambda addon: SimpleNamespace(jsonrpc=object(), notification=lambda *a, **k: None)
        module.SubtitleService = lambda *args: object()
        self.assertFalse(module.main(["plugin://x", "9", "?action=unknown"]))
        self.assertEqual(ended[-1][1]["succeeded"], False)




class DiagnosticsTests(unittest.TestCase):
    def test_bazarr_diagnostics_are_bounded_and_non_secret(self):
        settings = SimpleNamespace(
            bazarr=SimpleNamespace(
                enabled=True, url="https://private.example", api_key="secret",
                timeout=5, verify_tls=True, user_agent="Kodi-Managarr/test",
            ),
            bazarr_languages=["en", "fr:forced"],
        )
        fake = SimpleNamespace(
            last_operation="languages", last_category="success", last_status=None,
            status=lambda: {"bazarr_version": "1.5.6"},
            languages=lambda: [{"code2": "en"}, {"code2": "fr"}],
        )
        result = bazarr_diagnostics(settings, logger=None, client_class=lambda *args: fake)
        self.assertEqual(result["version"], "1.5.6")
        self.assertEqual(result["languageCount"], 2)
        self.assertEqual(result["availableLanguageCount"], 2)
        self.assertEqual(result["lastOperation"], "languages")
        self.assertNotIn("url", result)
        self.assertNotIn("api_key", result)


class SettingsSchemaTests(unittest.TestCase):
    def test_all_empty_string_defaults_explicitly_allow_empty(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        missing = []
        for setting in root.findall(".//setting"):
            default = setting.find("default")
            if setting.get("type") == "string" and default is not None and not (default.text or ""):
                allow = setting.find("constraints/allowempty")
                if allow is None or (allow.text or "").lower() != "true":
                    missing.append(setting.get("id"))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
