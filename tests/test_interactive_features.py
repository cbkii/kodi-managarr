import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions_interactive import InteractiveMixin
from arr_manager.errors import ConfigurationError, SafetyError
from arr_manager.models import SelectedItem


class UI:
    addon = None
    def __init__(self, choices=()):
        self.choices = list(choices); self.dialogs = []; self.notifications = []; self.texts = []
    def select(self, heading, options): return self.choices.pop(0) if self.choices else 0
    def confirm(self, heading, message): return True
    def ok(self, heading, message): self.dialogs.append((heading, message))
    def text(self, heading, message): self.texts.append((heading, message))
    def notification(self, message, **kwargs): self.notifications.append(message)


class Addon:
    def __init__(self): self.values = {}
    def getLocalizedString(self, value): return ""
    def setSetting(self, key, value): self.values[key] = value


class ServiceConfig:
    def __init__(self, enabled=True): self.enabled = enabled


class Settings:
    def __init__(self):
        self.addon = Addon(); self.prowlarr = ServiceConfig(False); self.bazarr = ServiceConfig(False)
        self.radarr = ServiceConfig(True); self.sonarr = ServiceConfig(True)
        self.request_radarr_root = "/movies"; self.request_radarr_profile = 1
        self.request_sonarr_root = "/tv"; self.request_sonarr_profile = 2
        self.request_sonarr_monitor = "future"
    def request_defaults_ready(self, service):
        return service in {"radarr", "sonarr"}


class Harness(InteractiveMixin):
    def __init__(self):
        self.settings = Settings(); self.ui = UI(); self.logger = mock.MagicMock()
        self._prowlarr = mock.MagicMock(); self._bazarr = mock.MagicMock()
        self.radarr = mock.MagicMock(); self.sonarr = mock.MagicMock()
    @property
    def prowlarr(self): return self._prowlarr
    @property
    def bazarr(self): return self._bazarr
    def _m(self, key, **values): return "Cancelled" if key == "cancelled" else key
    def _poll_command(self, client, response, description):
        if isinstance(response, Exception): raise response
        return {"status": "completed", "result": "successful"}


class InteractiveFeatureTests(unittest.TestCase):
    def movie(self):
        return SelectedItem(media_type="movie", title="Film", year=2024, unique_ids={"tmdb": "42"})

    def episode(self):
        return SelectedItem(media_type="episode", title="Episode", tvshow_title="Show", season=0, episode=1,
                            unique_ids={"tvdb": "99"})

    def test_existing_movie_is_monitored_and_searched_without_duplicate_add(self):
        h = Harness()
        h.radarr.movie_by_tmdb.return_value = {"id": 7, "title": "Film", "monitored": False}
        h.radarr.update_movie.return_value = {"id": 7, "title": "Film", "monitored": True}
        h.radarr.search_movie.return_value = {"id": 10}
        h._request_movie(self.movie())
        h.radarr.add_movie.assert_not_called()
        h.radarr.update_movie.assert_called_once()
        h.radarr.search_movie.assert_called_once_with(7)

    def test_absent_movie_is_added_rechecked_and_searched(self):
        h = Harness()
        h.radarr.movie_by_tmdb.side_effect = [None, {"id": 8, "title": "Film", "monitored": True}]
        h.radarr.lookup_movie.return_value = [{"tmdbId": 42, "title": "Film", "year": 2024}]
        h.radarr.search_movie.return_value = {"id": 11}
        h._request_movie(self.movie())
        payload = h.radarr.add_movie.call_args[0][0]
        self.assertEqual(payload["rootFolderPath"], "/movies")
        self.assertEqual(payload["qualityProfileId"], 1)
        self.assertFalse(payload["addOptions"]["searchForMovie"])

    def test_missing_defaults_fail_before_add(self):
        h = Harness(); h.settings.request_defaults_ready = lambda service: False
        h.radarr.movie_by_tmdb.return_value = None
        with self.assertRaises(ConfigurationError): h._request_movie(self.movie())
        h.radarr.add_movie.assert_not_called()

    def test_add_success_search_failure_reports_partial_success(self):
        h = Harness()
        h.radarr.movie_by_tmdb.side_effect = [None, {"id": 8, "title": "Film", "monitored": True}]
        h.radarr.lookup_movie.return_value = [{"tmdbId": 42, "title": "Film", "year": 2024}]
        h.radarr.search_movie.return_value = SafetyError("failed")
        with self.assertRaises(SafetyError): h._request_movie(self.movie())

    def test_episode_request_monitors_only_selected_episode(self):
        h = Harness()
        h.sonarr.series_by_tvdb.return_value = {"id": 5, "title": "Show", "monitored": True}
        h.sonarr.episodes.return_value = [{"id": 44, "seasonNumber": 0, "episodeNumber": 1, "monitored": False}]
        h.sonarr.search_episodes.return_value = {"id": 12}
        h._request_series_or_episode(self.episode())
        h.sonarr.set_episodes_monitored.assert_called_once_with([44], True)
        h.sonarr.search_episodes.assert_called_once_with([44])
        h.sonarr.search_series.assert_not_called()

    def test_interactive_grab_revalidates_release(self):
        h = Harness(); h.ui = UI([0])
        h.radarr.movie_by_tmdb.return_value = {"id": 7, "title": "Film"}
        release = {"guid": "g", "downloadUrl": "u", "indexerId": 1, "title": "R", "size": 1}
        h.radarr.releases.return_value = [release]
        h.interactive_search(self.movie())
        self.assertEqual(h.radarr.releases.call_count, 2)
        h.radarr.download_release.assert_called_once_with(release)

    def test_dashboard_isolates_optional_service_failure(self):
        h = Harness(); h.settings.prowlarr.enabled = True
        h.radarr.status.side_effect = RuntimeError("secret")
        h.sonarr.status.return_value = {"version": "4"}; h.sonarr.health.return_value = []
        h.sonarr.wanted_missing.return_value = {"totalRecords": 2}; h.sonarr.queue_overview.return_value = {"totalRecords": 0, "records": []}
        with mock.patch.object(Harness, "prowlarr", new_callable=mock.PropertyMock) as p:
            p.side_effect = RuntimeError("bad")
            text = h.dashboard()
        self.assertIn("Radarr: Unavailable (RuntimeError)", text)
        self.assertIn("Sonarr: 4", text)
        self.assertNotIn("secret", text)


if __name__ == "__main__":
    unittest.main()
