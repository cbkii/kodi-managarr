import importlib.util
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager import entrypoints
from arr_manager.errors import SafetyError
from arr_manager.kodi_selected import enrich_selected_series_identity
from arr_manager.models import SelectedItem
from arr_manager.registry import ACTION_REGISTRY
from arr_manager.resolver import resolve_series
from arr_manager.subtitle_service import SubtitleService, _select_results, selected_from_player


class ReleaseReadinessTests(unittest.TestCase):
    def test_registry_is_the_direct_action_source_of_truth_and_args_decode(self):
        registry_modes = {action["mode"] for action in ACTION_REGISTRY}
        self.assertEqual(entrypoints.REGISTERED_ACTION_MODES, registry_modes)
        self.assertTrue(registry_modes <= entrypoints.DIRECT_ACTIONS)
        self.assertEqual(
            entrypoints._parse_args(["?mode=request%5Fsearch&value=hello+world"]),
            {"mode": "request_search", "value": "hello world"},
        )
        self.assertEqual(entrypoints.ACTION_ALIASES["request_defaults"], "configure_request_defaults")

    def test_episode_parent_series_identity_is_enriched_and_episode_tvdb_is_not_reused(self):
        selected = SelectedItem(
            media_type="episode", db_id=44, title="Episode", tvshow_title="Show",
            tvshow_db_id=7, season=0, episode=1, unique_ids={"tvdb": "555"},
        )
        client = mock.MagicMock()
        client.tvshow_details.return_value = {
            "title": "Show", "year": 2020, "uniqueid": {"tvdb": "99", "imdb": "ttshow"},
        }
        enrich_selected_series_identity(selected, client)
        self.assertEqual(selected.series_year, 2020)
        self.assertEqual(selected.series_unique_ids["tvdb"], "99")

        sonarr = mock.MagicMock()
        sonarr.series_by_tvdb.return_value = {"id": 3, "title": "Show", "year": 2020}
        mapper = mock.MagicMock()
        resolved = resolve_series(selected, sonarr, mapper)
        self.assertEqual(resolved["id"], 3)
        sonarr.series_by_tvdb.assert_called_once_with(99)
        mapper.kodi_to_remote.assert_not_called()

    def test_subtitle_language_qualifiers_are_consistent_and_ordered(self):
        rows = [
            {"language": "en", "provider": "p", "score": 30},
            {"language": "en", "provider": "p", "score": 90, "forced": True},
            {"language": "en", "provider": "p", "score": 80, "hi": True},
            {"language": "fr", "provider": "p", "score": 70},
        ]
        self.assertEqual(
            [key for key, _ in _select_results(rows, ["fr", "en"])],
            ["fr", "en", "en:forced", "en:hi"],
        )
        self.assertEqual(
            [key for key, _ in _select_results(rows, ["en:forced"])],
            ["en:forced"],
        )

    def test_subtitle_cache_is_validated_and_single_use(self):
        with tempfile.TemporaryDirectory() as profile:
            service = SubtitleService.__new__(SubtitleService)
            service.profile = profile
            service.addon = mock.MagicMock()
            service.addon.getLocalizedString.return_value = ""
            service.logger = mock.MagicMock()
            payload = {
                "media_type": "movie", "kodi_db_id": 7, "radarr_id": 9,
                "language": "en:forced", "created": int(time.time()),
                "result": {
                    "provider": "provider", "subtitle": "opaque-id", "original_format": False,
                    "forced": True, "hearing_impaired": False, "hi": False,
                },
            }
            token = service._save_cache(payload)
            self.assertEqual(service._consume_cache(token), payload)
            with self.assertRaises(SafetyError):
                service._consume_cache(token)

            malformed = dict(payload)
            malformed["result"] = {"provider": "provider", "subtitle": "https://unsafe.example/token"}
            token = service._save_cache(malformed)
            with self.assertRaises(SafetyError):
                service._consume_cache(token)

    def test_playing_episode_uses_parent_tvshow_details(self):
        xbmc_module = types.SimpleNamespace(
            getInfoLabel=lambda key: {"VideoPlayer.DBTYPE": "episode", "VideoPlayer.DBID": "44"}.get(key, ""),
            Player=lambda: types.SimpleNamespace(getPlayingFile=lambda: "smb://server/Shows/Episode.mkv"),
        )
        kodi = mock.MagicMock()
        kodi.episode_details.return_value = {
            "title": "Episode", "season": 0, "episode": 1, "tvshowid": 7,
            "tvshowtitle": "Show", "uniqueid": {"tvdb": "555"},
        }
        kodi.tvshow_details.return_value = {
            "title": "Show", "year": 2020, "uniqueid": {"tvdb": "99"},
        }
        selected = selected_from_player(mock.MagicMock(), xbmc_module, kodi)
        self.assertEqual(selected.series_unique_ids, {"tvdb": "99"})
        self.assertEqual(selected.series_year, 2020)
        self.assertEqual((selected.season, selected.episode), (0, 1))


class SubtitleEntrypointTests(unittest.TestCase):
    def load_module(self):
        fake_plugin = types.SimpleNamespace(
            addDirectoryItem=mock.MagicMock(),
            endOfDirectory=mock.MagicMock(),
        )

        class ListItem:
            def __init__(self, **kwargs):
                self.path = ""
            def setPath(self, path):
                self.path = path

        modules = {
            "xbmcaddon": types.SimpleNamespace(Addon=lambda **kwargs: mock.MagicMock()),
            "xbmcgui": types.SimpleNamespace(ListItem=ListItem),
            "xbmcplugin": fake_plugin,
            "xbmcvfs": types.SimpleNamespace(),
        }
        spec = importlib.util.spec_from_file_location("managarr_subtitles_test", os.path.join(ROOT, "subtitles.py"))
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        module.xbmcplugin = fake_plugin
        module.Settings = lambda addon: types.SimpleNamespace(debug=False)
        module.KodiLogger = lambda debug: types.SimpleNamespace(debug_enabled=False, error=mock.MagicMock())
        module.KodiUI = lambda addon: types.SimpleNamespace(jsonrpc=object(), notification=mock.MagicMock())
        return module, fake_plugin

    def test_success_and_failure_are_reported_to_kodi_without_disk_cache(self):
        module, plugin = self.load_module()
        service = mock.MagicMock()
        service.search.return_value = []
        module.SubtitleService = lambda *args: service
        module.main(["plugin://context.arr.manager", "1", "?action=search"])
        plugin.endOfDirectory.assert_called_once_with(1, succeeded=True, cacheToDisc=False)

        module, plugin = self.load_module()
        service = mock.MagicMock()
        service.search.side_effect = RuntimeError("boom")
        module.SubtitleService = lambda *args: service
        module.main(["plugin://context.arr.manager", "2", "?action=search"])
        plugin.endOfDirectory.assert_called_once_with(2, succeeded=False, cacheToDisc=False)


if __name__ == "__main__":
    unittest.main()
